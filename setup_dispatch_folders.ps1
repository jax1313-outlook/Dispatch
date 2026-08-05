<#
.SYNOPSIS
    Creates the locked D:\ Dispatch ownership folder structure.

.DESCRIPTION
    Creates all required folders under D:\Dispatch Operations, D:\Archive,
    and D:\Memory. Sets the five environment variables via setx so they
    persist across reboots.

    Safe to run more than once — creates missing folders only, never
    deletes or overwrites anything.

    IMPORTANT: setx writes to the Windows registry. The new values are
    picked up by NEW PowerShell/cmd sessions only. The current session
    keeps its old environment until you close and reopen it.

.PARAMETER DryRun
    Show what would be created without making any changes.

.EXAMPLE
    .\setup_dispatch_folders.ps1
    .\setup_dispatch_folders.ps1 -DryRun
#>

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# ── Root paths ────────────────────────────────────────────────────────

$OpsRoot     = "D:\Dispatch Operations"
$ArchiveRoot = "D:\Archive"
$MemoryRoot  = "D:\Memory"

# ── Full folder tree ──────────────────────────────────────────────────

$folders = @(
    # Dispatch Operations
    "$OpsRoot\Code"
    "$OpsRoot\Constitution"
    "$OpsRoot\Context"
    "$OpsRoot\Config"
    "$OpsRoot\Launchers"
    "$OpsRoot\Logs"
    "$OpsRoot\Temp"
    "$OpsRoot\Current Workspace"
    "$OpsRoot\Current Workspace\PortalData"
    "$OpsRoot\Deployment"

    # Archive
    "$ArchiveRoot\CIN\Raw"
    "$ArchiveRoot\CIN\Processed"
    "$ArchiveRoot\CIN\Intelligence"
    "$ArchiveRoot\CIN\Summaries"
    "$ArchiveRoot\CIN\Routing"
    "$ArchiveRoot\CIN\Proposals"
    "$ArchiveRoot\CIN\Pending"
    "$ArchiveRoot\CIN\Outbox"
    "$ArchiveRoot\Loads"
    "$ArchiveRoot\POD"
    "$ArchiveRoot\Retention"
    "$ArchiveRoot\Reports"
    "$ArchiveRoot\Historical Records"

    # Memory
    "$MemoryRoot\Company Library"
    "$MemoryRoot\Broker Library"
    "$MemoryRoot\Customer Library"
    "$MemoryRoot\Location Intelligence"
    "$MemoryRoot\Operational Intelligence"
    "$MemoryRoot\Forms"
    "$MemoryRoot\Templates"
    "$MemoryRoot\Procedures"
    "$MemoryRoot\Manuals"
    "$MemoryRoot\Receipts"
    "$MemoryRoot\Fuel"
    "$MemoryRoot\Compliance"
    "$MemoryRoot\Equipment"
    "$MemoryRoot\Drivers"
    "$MemoryRoot\Insurance"
    "$MemoryRoot\Certifications"
    "$MemoryRoot\Evidence"
    "$MemoryRoot\Documents"
)

# ── Environment variables (persisted via setx) ───────────────────────
# setx writes to HKCU\Environment in the registry.
# New values are NOT available in the current session — you must open
# a new PowerShell or cmd window to see them.

$envVars = @{
    "DISPATCH_OPERATIONS_ROOT" = $OpsRoot
    "DISPATCH_ARCHIVE_ROOT"    = $ArchiveRoot
    "DISPATCH_MEMORY_ROOT"     = $MemoryRoot
    "DISPATCH_ARCHIVE_PATH"    = "$ArchiveRoot\CIN"
    "PORTAL_DATA_DIR"          = "$OpsRoot\Current Workspace\PortalData"
}

# ── Preflight: check D:\ exists ──────────────────────────────────────

if (-not (Test-Path "D:\")) {
    Write-Host ""
    Write-Host "  WARNING: Drive D:\ does not exist on this machine." -ForegroundColor Red
    Write-Host "  This script expects a D:\ drive (internal, external, or mapped)."
    Write-Host "  Plug in the drive or map a volume to D:\ and run again."
    Write-Host ""
    exit 1
}

# ── Banner ────────────────────────────────────────────────────────────

Write-Host ""
if ($DryRun) {
    Write-Host "  DRY RUN -- no changes will be made" -ForegroundColor Yellow
} else {
    Write-Host "  DISPATCH Folder Setup" -ForegroundColor Cyan
}
Write-Host ""

# ── Create folders ────────────────────────────────────────────────────

$created = 0
$existed = 0

foreach ($path in $folders) {
    if (Test-Path $path) {
        $existed++
    } else {
        if ($DryRun) {
            Write-Host "  [WOULD CREATE] $path" -ForegroundColor Yellow
        } else {
            New-Item -ItemType Directory -Path $path -Force | Out-Null
            Write-Host "  [CREATED] $path" -ForegroundColor Green
        }
        $created++
    }
}

# ── Set environment variables ─────────────────────────────────────────

$varsSet = 0

foreach ($entry in $envVars.GetEnumerator()) {
    $current = [System.Environment]::GetEnvironmentVariable($entry.Key, "User")
    if ($current -eq $entry.Value) {
        # Already set to the correct value — skip
    } else {
        if ($DryRun) {
            if ($current) {
                Write-Host "  [WOULD UPDATE] $($entry.Key) = $($entry.Value)" -ForegroundColor Yellow
                Write-Host "                 (currently: $current)" -ForegroundColor DarkGray
            } else {
                Write-Host "  [WOULD SET]    $($entry.Key) = $($entry.Value)" -ForegroundColor Yellow
            }
        } else {
            setx $entry.Key $entry.Value | Out-Null
            Write-Host "  [SET] $($entry.Key) = $($entry.Value)" -ForegroundColor Green
        }
        $varsSet++
    }
}

# ── Report ────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "  -- Summary --" -ForegroundColor Cyan
Write-Host "  Folders created:  $created"
Write-Host "  Folders existed:  $existed"
Write-Host "  Env vars set:     $varsSet"
Write-Host ""

if (-not $DryRun -and $varsSet -gt 0) {
    Write-Host "  NOTE: Environment variables were set via setx." -ForegroundColor Yellow
    Write-Host "  They will NOT be visible in this session." -ForegroundColor Yellow
    Write-Host "  Close this window and open a new PowerShell to use them." -ForegroundColor Yellow
    Write-Host ""
}

if ($DryRun) {
    Write-Host "  Dry run complete. Run without -DryRun to apply." -ForegroundColor Yellow
} else {
    Write-Host "  Setup complete." -ForegroundColor Green
}
Write-Host ""
