<#
.SYNOPSIS
    Dispatch - Operations Control.

.DESCRIPTION
    Start, stop, restart, open or inspect the Dispatch operations portal.

    This wrapper holds no logic on purpose. Everything that decides anything --
    whether Dispatch is running, which process is the server, whether it is safe
    to start another one, what a failure means in plain language -- lives in the
    dispatch_launcher Python package, which the repository test suite exercises.
    A PowerShell script in this repository cannot be tested, so it is not
    allowed to make decisions.

    Run with no arguments for the interactive menu.

.PARAMETER Action
    One of: menu, status, start, stop, restart, open. Defaults to menu.

.EXAMPLE
    .\Dispatch.ps1
    .\Dispatch.ps1 status
    .\Dispatch.ps1 restart
#>

param(
    [ValidateSet("menu", "status", "start", "stop", "restart", "open")]
    [string]$Action = "menu"
)

$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

# Prefer the Windows Python launcher, which is installed alongside Python and
# resolves a real interpreter even when PATH does not.
$python = "python"
$arguments = @("-m", "dispatch_launcher", $Action)
if (Get-Command py -ErrorAction SilentlyContinue) {
    $python = "py"
    $arguments = @("-3", "-m", "dispatch_launcher", $Action)
}

& $python @arguments
exit $LASTEXITCODE
