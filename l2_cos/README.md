# L2-COS — Dispatch

A clone-and-repurpose of the cin_lite pipeline (Rule 15: Reuse Before
Create) for freight dispatch. Runs with zero setup on bundled sample data.

```bash
python -m l2_cos.run                    # interactive: choose an action per load
python -m l2_cos.run --action BOOKED    # non-interactive (applies to all)
```

Each run flows one or more loads through:

```
acquire -> look up Location/Broker intelligence (capture once, Rule 14)
        -> process (6 rule modules) -> dispatch control email
        -> human confirms stage -> archive + advance lifecycle
        -> publisher-eligible flag once Intelligence Score >= 90 (Rule 4)
```

and writes artifacts into `Archive/{Raw,Processed,Intelligence,Dispatch}/`
plus the two intelligence libraries under `Archive/{Locations,Brokers}/`,
keyed by a unique ID like `LOAD-20260727-E8B07B86`.

## Layout (maps 1:1 to the cin_lite architecture layers)

| File | Layer | Responsibility |
|------|-------|----------------|
| `acquisition.py` | Acquisition | Generic load-board HTTP adapter (falls back to `sample_data/`) |
| `intelligence_store.py` | Acquisition (Rule 14) | Loads the Location/Broker Intelligence Libraries once |
| `rules/` + `processing.py` | Processing | 6 deterministic rule modules -> `IntelligenceScore` JSON |
| `control.py` | Control | Renders the dispatch checkbox email; the action IS the target `LifecycleStage` |
| `archive.py` | Archive | `LOAD-YYYYMMDD-<hash>` IDs, folder-tree persistence, library capture |
| `run.py` | Automation | Orchestrates the above end-to-end |
| `models/state.py` | — | The 11-stage `LifecycleStage` lock + `Load` |
| `models/intelligence.py` | — | `LocationIntelligence`, `BrokerIntelligence`, `IntelligenceScore`, `InquiryArtifacts` |

## The state model lock (System Rule 3)

`Load.stage` only ever advances forward, one stage at a time:

```
Available -> Booked -> Planned -> En Route -> At Pickup -> Loaded
          -> In Transit -> At Delivery -> Delivered -> Invoiced -> Closed
```

`Load.advance(target, actor)` raises `ValueError` on any skip or reversal.
Because the chain is strictly linear, a control action key IS the target
stage's value (e.g. `"BOOKED"`); `hold_for_review` is the one action that
never mutates `stage`.

## Rule modules

Each module takes the raw load dict plus the looked-up facility/broker
records and returns an `IntelligenceScore` (module/version/score/flags/findings —
the same shape as cin_lite's `RuleResult`, with a mandatory 0-100 score):

- `lane_fit` — does the lane match the broker's `preferred_lanes`?
- `rate_anomaly` — is `rate_per_mile` within band of the broker's `historical_rates`?
- `facility_risk` — pickup/delivery `historical_problems` + `security_requirements`
- `broker_risk` — slow payment terms, incomplete contact record
- `capacity_match` — does `equipment_type` match the fleet's available equipment?
- `deadhead_cost` — deadhead-to-loaded-miles ratio

`processing.overall_score()` is the mean of all six, rounded — the value
checked against `l2_cos.models.intelligence.PUBLISH_THRESHOLD` (90) to flag
publisher eligibility (System Rule 4). The publisher workflow itself (auto
building the `InquiryArtifacts` packet and sending the inquiry) is not yet
wired into `run.py` — `Load.intelligence_score` and `InquiryArtifacts` are in
place for it.

## Add a rule

Create `rules/your_rule.py` exposing `NAME`, `VERSION`, and
`run(load, *, facility_pickup=None, facility_delivery=None, broker=None) -> IntelligenceScore`,
then append the module to `ALL_RULES` in `rules/__init__.py`. Keep rules
deterministic (no LLM/network in the rule path), matching cin_lite's rule
framework.

## Acquisition — generic load-board adapter

`acquisition.py` is a provider-agnostic HTTP adapter, not a specific load
board's real schema — point it at whatever provider you integrate (DAT,
Truckstop, a private broker feed, ...) and adjust `_map_load`'s field names
to match.

```bash
export L2_COS_LOAD_BOARD_URL=https://your-provider.example/loads
export L2_COS_LOAD_BOARD_API_KEY=...       # sent as Authorization: Bearer <key>
python -m l2_cos.run --action BOOKED
```

Without `L2_COS_LOAD_BOARD_URL` — or when a request fails — it falls back to
`sample_data/sample_load_*.json`, so the zero-setup demo still runs.

## Tests

```bash
pip install pytest pytest-cov
python -m pytest --cov=l2_cos --cov-report=term-missing
```

Coverage: all six rule modules (positive + negative + determinism), the
intelligence-library loader, the load-board adapter (success, HTTP error
fallback, network error fallback), the control layer (action set, email
rendering, illegal-transition rejection), the archive layer (ID format,
all six artifact writers), and a full end-to-end `run.py` walk. Fixtures
(`tests/conftest.py`) provide a clean and a risky load/broker pair; every
test redirects archive writes to a tmp dir, so the suite is offline,
deterministic, and side-effect-free.
