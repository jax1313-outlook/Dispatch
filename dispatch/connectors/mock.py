"""The one mock connector — SIMULATED on every path, including the failing ones.

Section 6.6 asks for a single safe mock that "returns clearly SIMULATED data,
exercises the full contract including error, retry, and audit paths, and is used
by the connector tests". Route Risk is the subject, because it is the connector
whose real provider is furthest away and whose evaluation layer needs something
to evaluate.

Three deliberate properties:

**It cannot produce anything but SIMULATED.** Every payload it builds passes
``ConnectorStatus.SIMULATED``, its configuration reports SIMULATED, its provider
is named "Dispatch Mock Provider (no external system)", and its condition
summaries carry the word in their text as well as their status field -- because a
summary string is what ends up in an email or a note, and a status field does not
travel into a sentence. There is no flag that makes it claim more; the mission's
rule is that mock data must never appear unlabelled anywhere, and the cheapest
way to keep that true is to leave no code path that could.

**It fails on demand, in the ways that matter.** ``failure_mode`` drives a
timeout (retryable, and retried), an authentication failure (not retryable, and
not retried -- retrying a rejected credential is how an account gets locked), and
a malformed provider response (the provider answered, the answer could not be
normalized). Those are the three failure tests Section 6.8 names, and having one
object produce all three means the tests exercise the real classification code
rather than three hand-built results. A fourth mode, ``crash``, raises instead
of returning at all, so the contract's promise that ``fetch`` always answers is
proven against a connector that breaks it.

**It includes a boundary probe, and this is the interesting one.** With
``failure_mode="boundary_probe"`` the mock reaches for a database connection the
way a real provider SDK would -- dynamically, at call time, through
``__import__`` -- which is precisely the case the static import scan cannot see.
That is not a loophole being demonstrated for its own sake: it is the reason
``boundary.sealed()`` exists at all, and having a connector in the package that
actually attempts it means the runtime seal is proven against a real attempt
rather than a hypothetical one. Called through ``boundary.execute`` the probe
raises ``BoundaryViolation``; called directly, outside the seal, it opens an
in-memory database and touches nothing.
"""

from __future__ import annotations

from dispatch.connectors.contract import (
    AuthenticationStatus,
    BaseConnector,
    CapabilityDeclaration,
    ConfigurationStatus,
    ConnectorError,
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    HealthStatus,
    RetryStatus,
    attempt,
    utc_now,
)
from dispatch.connectors.route_risk_connector import (
    PAYLOAD_KIND,
    ROUTE_RISK_COLLECTIBLES,
    RouteCondition,
    normalize_conditions,
)

#: The conditions the mock always reports. Fixed rather than random: a mock that
#: varies its output makes a failing test a puzzle, and there is nothing to be
#: learned from a different fictional storm each run.
SIMULATED_CONDITIONS: tuple[dict, ...] = (
    {
        "kind": "weather",
        "summary": "SIMULATED: freezing rain advisory across the I-75 corridor north of Macon",
        "affected_area": "Middle Georgia",
        "affected_corridor": "I-75 N, exits 165-201",
        "severity_hint": "warning",
    },
    {
        "kind": "road_restrictions",
        "summary": "SIMULATED: right lane closed for bridge work, US-441 at the Oconee river",
        "affected_area": "Athens, GA",
        "affected_corridor": "US-441 S",
        "severity_hint": "advisory",
    },
)

#: What the mock's "provider" returns in ``malformed`` mode: an answer that
#: arrived and cannot be normalized. A condition class that is not one of
#: Section 6.5's is exactly the shape of a real provider adding a category.
MALFORMED_RESPONSE: dict = {"kind": "sasquatch_sighting", "summary": "not a route condition"}

FAILURE_MODES: tuple[str, ...] = ("", "timeout", "auth", "malformed", "crash", "boundary_probe")


class MockRouteRiskConnector(BaseConnector):
    """A Route Risk provider that does not exist, saying so on every field."""

    connector_id = "mock.route_risk"
    connector_name = "Mock Route Risk Connector"
    provider_id = "dispatch-mock"
    provider_name = "Dispatch Mock Provider (no external system)"
    required_config_keys = ()
    credential_keys = ()
    auth_method = "none"
    capability_declaration = CapabilityDeclaration(
        collects=ROUTE_RISK_COLLECTIBLES,
        produces=("SIMULATED route conditions in the Route Risk normalized shape",),
        notes=(
            "A stand-in for a Route Risk provider. Everything it returns is fictional and "
            "labelled SIMULATED, in the status field and in the text."
        ),
    )

    def __init__(self, *, failure_mode: str = "", succeed_after: int = 0) -> None:
        """``succeed_after`` makes the timeout mode recoverable.

        With ``failure_mode="timeout"`` and ``succeed_after=2``, the first
        attempt times out and the second succeeds -- the case a retry policy
        exists for, and the one a mock that could only fail permanently would
        never let a test see.
        """
        if failure_mode not in FAILURE_MODES:
            raise ValueError(
                f"{failure_mode!r} is not a mock failure mode: {', '.join(m or '(success)' for m in FAILURE_MODES)}"
            )
        self.failure_mode = failure_mode
        self.succeed_after = succeed_after
        self.attempt_count = 0
        self.last_attempt_at = ""
        self.last_success_at = ""

    # ---------------------------------------------------------------- status

    def configuration(self) -> ConfigurationStatus:
        return ConfigurationStatus(
            ConnectorStatus.SIMULATED,
            detail=(
                "This is a mock. It has no configuration because it has no external system "
                "behind it, and everything it returns is fictional."
            ),
        )

    def authentication(self) -> AuthenticationStatus:
        return AuthenticationStatus(
            ConnectorStatus.SIMULATED,
            method="none",
            detail="No credentials exist for a system that does not exist.",
        )

    def health(self) -> HealthStatus:
        return HealthStatus(
            ConnectorStatus.SIMULATED,
            last_attempt_at=self.last_attempt_at,
            last_success_at=self.last_success_at,
        )

    # ---------------------------------------------------------------- the verb

    def fetch(self, request: ConnectorRequest) -> ConnectorResult:
        self.last_attempt_at = utc_now()

        if self.failure_mode == "crash":
            # A provider library that raises instead of returning. The contract
            # says a connector answers with a result; boundary.execute() is what
            # holds that true for a connector that does not, and this mode is
            # how that is proven with a connector inside the package rather than
            # a test double outside it.
            raise RuntimeError("mock provider library raised instead of returning a result")

        if self.failure_mode == "auth":
            # One attempt, no retry, whatever max_attempts says.
            return self.failure(
                request,
                ConnectorError(
                    "auth_failure",
                    "The mock provider rejected the credentials. Not retried: a rejected "
                    "credential does not become valid on a second attempt.",
                    retryable=False,
                ),
                status=ConnectorStatus.UNAVAILABLE,
                retry=RetryStatus(1, request.max_attempts, False, 0.0),
            )

        if self.failure_mode == "boundary_probe":
            return self._boundary_probe(request)

        value, retry, error = attempt(
            self._call_provider,
            max_attempts=request.max_attempts,
            retry_on=(TimeoutError,),
            backoff_seconds=5.0,
        )

        if error is not None:
            if isinstance(error, TimeoutError):
                return self.failure(
                    request,
                    ConnectorError(
                        "timeout",
                        f"The mock provider did not answer within {request.timeout_seconds}s "
                        f"after {retry.attempts} attempt(s).",
                        retryable=True,
                        detail=str(error),
                    ),
                    status=ConnectorStatus.UNAVAILABLE,
                    retry=retry,
                )
            return self.failure(
                request,
                ConnectorError(
                    "malformed_payload",
                    "The mock provider answered with something that is not a route condition, "
                    "so nothing could be normalized.",
                    retryable=False,
                    detail=str(error),
                ),
                status=ConnectorStatus.UNAVAILABLE,
                retry=retry,
            )

        self.last_success_at = utc_now()
        payload = self.payload(
            PAYLOAD_KIND,
            normalize_conditions(value or (), load_id=str(request.params.get("load_id", ""))),
            status=ConnectorStatus.SIMULATED,
            source_reference="dispatch-mock://route-risk/simulated",
            source_timestamp=utc_now(),
            confidence=0.0,
        )
        return self.success(request, payload, retry=retry)

    def _call_provider(self) -> tuple[RouteCondition, ...]:
        """Stands where an HTTP call would stand."""
        self.attempt_count += 1

        if self.failure_mode == "timeout":
            if not self.succeed_after or self.attempt_count < self.succeed_after:
                raise TimeoutError("mock provider timed out")
        if self.failure_mode == "malformed":
            # RouteCondition refuses an unknown condition class, which is how a
            # provider's unrecognised category becomes a labelled failure rather
            # than a silently dropped field.
            return (RouteCondition(**MALFORMED_RESPONSE),)

        return tuple(RouteCondition(**raw) for raw in SIMULATED_CONDITIONS)

    def _boundary_probe(self, request: ConnectorRequest) -> ConnectorResult:
        """Reach for a database the way a provider SDK would, and be stopped.

        ``__import__`` rather than a normal import so that the static scan in
        ``boundary.verify_package`` cannot see it -- which is the entire point.
        Under ``boundary.execute`` this raises ``BoundaryViolation`` before the
        connection is made. Outside the seal it opens an in-memory database,
        writes nothing, and returns a SIMULATED payload saying it got through,
        so a test can tell the two situations apart.
        """
        sqlite = __import__("sqlite3")
        connection = sqlite.connect(":memory:")
        connection.close()
        payload = self.payload(
            PAYLOAD_KIND,
            normalize_conditions((), load_id=""),
            status=ConnectorStatus.SIMULATED,
            source_reference="dispatch-mock://route-risk/boundary-probe",
            source_timestamp=utc_now(),
        )
        return self.success(request, payload)
