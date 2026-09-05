<#
.SYNOPSIS
    D:\ Forensic Inventory Collector - READ ONLY.

.DESCRIPTION
    Walks a drive and records evidence for a forensic inventory. It is strictly
    read-only: it opens files for reading to hash them and does nothing else.

    It NEVER builds, modifies, moves, deletes, renames, merges or reorganizes
    anything. It runs no git command that can write (no fetch, pull, checkout,
    gc, or config change). Every git call is a plain-text read.

    Output is a folder of CSV/JSON evidence files plus a summary, ready to be
    zipped and handed back for analysis.

.PARAMETER Root
    Drive or folder to inventory. Default D:\

.PARAMETER OutDir
    Where to write evidence. Default C:\DDriveForensics_<timestamp>
    NOTE: choose a path OUTSIDE the Root so collection never writes into evidence.

.PARAMETER MaxHashBytes
    Files larger than this are recorded but not hashed. Default 100MB.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Collect-DDriveForensics.ps1

.NOTES
    Requires PowerShell 5.1+ (ships with Windows 10/11). Run as a normal user;
    Administrator only if some folders are ACL-blocked. Expect 20-90 minutes
    for a large drive - hashing is the slow part.
#>
[CmdletBinding()]
param(
    [string]$Root = 'D:\',
    [string]$OutDir = "C:\DDriveForensics_$(Get-Date -Format 'yyyyMMdd_HHmmss')",
    [long]$MaxHashBytes = 100MB,

    # Git object/pack internals are excluded by default: they are opaque, they
    # dominate file counts, and every tracked blob is already captured exactly
    # in git_tracked_blobs.csv. Set this to inventory them as raw files too.
    [switch]$IncludeGitInternals
)

$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'Continue'

if (-not (Test-Path -LiteralPath $Root)) {
    Write-Error "Root '$Root' does not exist or is not reachable from this machine."
    exit 1
}
if ($OutDir -like "$($Root.TrimEnd('\'))*") {
    Write-Error "OutDir must be OUTSIDE Root so collection never writes into the evidence being collected."
    exit 1
}
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$errLog = Join-Path $OutDir 'errors.log'
function Log-Err($msg) { Add-Content -LiteralPath $errLog -Value "$(Get-Date -Format o)`t$msg" }

Write-Host "D:\ FORENSIC INVENTORY COLLECTOR (read-only)" -ForegroundColor Cyan
Write-Host "  Root  : $Root"
Write-Host "  Output: $OutDir"
Write-Host ""

# ---------------------------------------------------------------- helpers ----

# Git blob SHA-1: sha1("blob " + <bytelength> + "\0" + <bytes>).
# This is the SAME identifier git uses, so results join directly against the
# GitHub repository inventory already collected.
$sha1 = [System.Security.Cryptography.SHA1]::Create()
$sha256 = [System.Security.Cryptography.SHA256]::Create()

function Get-GitBlobSha1 {
    param([string]$Path, [long]$Length)
    try {
        $header = [System.Text.Encoding]::ASCII.GetBytes("blob $Length" + [char]0)
        $fs = [System.IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite')
        try {
            $ms = New-Object System.IO.MemoryStream
            $ms.Write($header, 0, $header.Length)
            $fs.CopyTo($ms)
            $ms.Position = 0
            ($sha1.ComputeHash($ms) | ForEach-Object { $_.ToString('x2') }) -join ''
        } finally { $fs.Dispose() }
    } catch { Log-Err "sha1`t$Path`t$($_.Exception.Message)"; 'ERROR' }
}

function Get-Sha256 {
    param([string]$Path)
    try {
        $fs = [System.IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite')
        try { ($sha256.ComputeHash($fs) | ForEach-Object { $_.ToString('x2') }) -join '' }
        finally { $fs.Dispose() }
    } catch { Log-Err "sha256`t$Path`t$($_.Exception.Message)"; 'ERROR' }
}

function Get-FirstLine {
    param([string]$Path)
    try {
        $r = New-Object System.IO.StreamReader($Path)
        try {
            for ($i = 0; $i -lt 5; $i++) {
                $l = $r.ReadLine()
                if ($null -eq $l) { break }
                $l = $l.Trim()
                if ($l) { return ($l -replace '[\r\n\t]', ' ').Substring(0, [Math]::Min(200, $l.Length)) }
            }
            ''
        } finally { $r.Dispose() }
    } catch { '' }
}

# ------------------------------------------------------- 1. FILE INVENTORY ----

Write-Host "[1/6] Enumerating files (this is the long pass)..." -ForegroundColor Yellow

$DOC_EXT     = @('.md','.txt','.rst','.adoc')
$OFFICE_EXT  = @('.docx','.doc','.pdf','.xlsx','.xls','.pptx','.ppt','.rtf','.odt')
$CODE_EXT    = @('.py','.js','.ts','.tsx','.jsx','.ps1','.psm1','.bat','.cmd','.sh','.sql','.html','.css','.java','.cs','.go','.rb','.php')
$DATA_EXT    = @('.json','.yaml','.yml','.toml','.ini','.cfg','.xml','.csv','.tsv')
$DB_EXT      = @('.db','.sqlite','.sqlite3','.db3','.mdb','.accdb')
$ARCHIVE_EXT = @('.zip','.7z','.rar','.tar','.gz','.tgz','.bz2','.xz','.cab','.iso')

$filesCsv = Join-Path $OutDir 'files.csv'
'FullPath,RelPath,Name,Extension,Category,SizeBytes,LastWriteUtc,CreationUtc,GitBlobSha1,Sha256,FirstLine,InGitRepo' |
    Set-Content -LiteralPath $filesCsv -Encoding UTF8

# Matches a .git directory component on Windows or POSIX separators.
$GIT_INTERNAL = '[\\/]\.git[\\/]'

$count = 0; $skippedGit = 0; $bytes = 0; $sw = [Diagnostics.Stopwatch]::StartNew()
$rootLen = $Root.TrimEnd('\').Length + 1
$batch = New-Object System.Collections.Generic.List[string]

Get-ChildItem -LiteralPath $Root -Recurse -File -Force -ErrorAction SilentlyContinue |
ForEach-Object {
    $f = $_

    $isGitInternal = ($f.FullName -match $GIT_INTERNAL)
    if ($isGitInternal -and -not $IncludeGitInternals) { $skippedGit++; return }

    $count++; $bytes += $f.Length

    if ($count % 2000 -eq 0) {
        Write-Host ("    {0,9:N0} files  {1,8:N1} GB  {2:N0}s  {3}" -f `
            $count, ($bytes/1GB), $sw.Elapsed.TotalSeconds, $f.DirectoryName) -ForegroundColor DarkGray
        Add-Content -LiteralPath $filesCsv -Value $batch -Encoding UTF8
        $batch.Clear()
    }

    $ext = $f.Extension.ToLowerInvariant()
    $cat = switch -Regex ($ext) {
        '^\.(md|txt|rst|adoc)$'                          { 'DOC';     break }
        '^\.(docx|doc|pdf|xlsx|xls|pptx|ppt|rtf|odt)$'    { 'OFFICE';  break }
        '^\.(py)$'                                       { 'PYTHON';  break }
        '^\.(js|ts|tsx|jsx|java|cs|go|rb|php|sql|html|css)$' { 'CODE'; break }
        '^\.(ps1|psm1|bat|cmd|sh)$'                      { 'SCRIPT';  break }
        '^\.(json|yaml|yml|toml|ini|cfg|xml|csv|tsv)$'    { 'DATA';    break }
        '^\.(db|sqlite|sqlite3|db3|mdb|accdb)$'           { 'DATABASE';break }
        '^\.(zip|7z|rar|tar|gz|tgz|bz2|xz|cab|iso)$'      { 'ARCHIVE'; break }
        default                                          { 'OTHER' }
    }

    # Hash everything we can. Large files: size+mtime identity only.
    $blob = ''; $s256 = ''
    if ($f.Length -le $MaxHashBytes) {
        $blob = Get-GitBlobSha1 -Path $f.FullName -Length $f.Length
        if ($cat -in @('ARCHIVE','DATABASE','OFFICE')) { $s256 = Get-Sha256 -Path $f.FullName }
    } else {
        $blob = 'SKIPPED-LARGE'
    }

    $first = ''
    if ($cat -in @('DOC','DATA') -and $f.Length -lt 2MB) { $first = Get-FirstLine -Path $f.FullName }

    $inGit = if ($isGitInternal) { 'GITINTERNAL' } else { '' }

    $rel = if ($f.FullName.Length -gt $rootLen) { $f.FullName.Substring($rootLen) } else { $f.FullName }
    $esc = { param($s) if ($null -eq $s) { '""' } else { '"' + ($s -replace '"','""') + '"' } }

    $batch.Add(( @(
        (& $esc $f.FullName), (& $esc $rel), (& $esc $f.Name), (& $esc $ext), (& $esc $cat),
        $f.Length,
        (& $esc $f.LastWriteTimeUtc.ToString('o')),
        (& $esc $f.CreationTimeUtc.ToString('o')),
        (& $esc $blob), (& $esc $s256), (& $esc $first), (& $esc $inGit)
    ) -join ','))
}

if ($batch.Count) { Add-Content -LiteralPath $filesCsv -Value $batch -Encoding UTF8 }
$sw.Stop()
Write-Host ("    DONE: {0:N0} files, {1:N1} GB, {2:N0}s  (skipped {3:N0} .git internals)" -f `
    $count, ($bytes/1GB), $sw.Elapsed.TotalSeconds, $skippedGit) -ForegroundColor Green

# -------------------------------------------------------- 2. DIRECTORY MAP ----

Write-Host "[2/6] Directory map..." -ForegroundColor Yellow
$dirs = Get-ChildItem -LiteralPath $Root -Recurse -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch $GIT_INTERNAL } |
    ForEach-Object {
        $d = $_
        [pscustomobject]@{
            FullPath     = $d.FullName
            Depth        = ($d.FullName.Split('\').Count - 1)
            Name         = $d.Name
            LastWriteUtc = $d.LastWriteTimeUtc.ToString('o')
            CreationUtc  = $d.CreationTimeUtc.ToString('o')
        }
    }
$dirs | Export-Csv -LiteralPath (Join-Path $OutDir 'directories.csv') -NoTypeInformation -Encoding UTF8
Write-Host ("    {0:N0} directories" -f $dirs.Count) -ForegroundColor Green

# ------------------------------------------------------- 3. GIT REPOSITORIES --

Write-Host "[3/6] Git working trees (read-only git calls)..." -ForegroundColor Yellow
$hasGit = [bool](Get-Command git -ErrorAction SilentlyContinue)
if (-not $hasGit) { Write-Warning "  git not on PATH - recording .git locations only, no metadata." }

$gitDirs = Get-ChildItem -LiteralPath $Root -Recurse -Directory -Force -Filter '.git' -ErrorAction SilentlyContinue
$repos = foreach ($g in $gitDirs) {
    $work = Split-Path $g.FullName -Parent
    $o = [ordered]@{
        WorkTree = $work; GitDir = $g.FullName
        Remotes = ''; CurrentBranch = ''; HeadSha = ''; HeadDateUtc = ''; HeadSubject = ''
        LocalBranches = ''; LocalBranchCount = 0; CommitCount = ''; DirtyFileCount = ''
        UntrackedCount = ''; StashCount = ''; TrackedFileCount = ''; Tags = ''
    }
    if ($hasGit) {
        try {
            $ge = @('-C', $work, '--no-pager')
            $o.Remotes          = ((& git @ge remote -v 2>$null) -join ' | ')
            $o.CurrentBranch    = (& git @ge rev-parse --abbrev-ref HEAD 2>$null)
            $o.HeadSha          = (& git @ge rev-parse HEAD 2>$null)
            $o.HeadDateUtc      = (& git @ge log -1 --format='%cI' 2>$null)
            $o.HeadSubject      = (& git @ge log -1 --format='%s' 2>$null)
            $br                 = @(& git @ge branch --format='%(refname:short)' 2>$null)
            $o.LocalBranches    = ($br -join ';')
            $o.LocalBranchCount = $br.Count
            $o.CommitCount      = (& git @ge rev-list --count HEAD 2>$null)
            $st                 = @(& git @ge status --porcelain 2>$null)
            $o.DirtyFileCount   = @($st | Where-Object { $_ -notmatch '^\?\?' }).Count
            $o.UntrackedCount   = @($st | Where-Object { $_ -match '^\?\?' }).Count
            $o.StashCount       = @(& git @ge stash list 2>$null).Count
            $o.TrackedFileCount = @(& git @ge ls-files 2>$null).Count
            $o.Tags             = ((& git @ge tag 2>$null) -join ';')
        } catch { Log-Err "git`t$work`t$($_.Exception.Message)" }
    }
    [pscustomobject]$o
}
$repos | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $OutDir 'git_repos.json') -Encoding UTF8
$repos | Export-Csv -LiteralPath (Join-Path $OutDir 'git_repos.csv') -NoTypeInformation -Encoding UTF8
Write-Host ("    {0} git working trees" -f @($repos).Count) -ForegroundColor Green

# --- every tracked blob in every repo, for join against the GitHub inventory ---
if ($hasGit) {
    $blobCsv = Join-Path $OutDir 'git_tracked_blobs.csv'
    'WorkTree,Ref,BlobSha1,Path' | Set-Content -LiteralPath $blobCsv -Encoding UTF8
    foreach ($r in $repos) {
        try {
            $ge = @('-C', $r.WorkTree, '--no-pager')
            foreach ($ref in @(& git @ge for-each-ref --format='%(refname:short)' refs/heads refs/remotes 2>$null)) {
                foreach ($line in (& git @ge ls-tree -r $ref 2>$null)) {
                    if ($line -match '^\d+\s+blob\s+([0-9a-f]{40})\s+(.+)$') {
                        Add-Content -LiteralPath $blobCsv -Encoding UTF8 -Value (
                            '"{0}","{1}","{2}","{3}"' -f
                            ($r.WorkTree -replace '"','""'), ($ref -replace '"','""'), $Matches[1], ($Matches[2] -replace '"','""'))
                    }
                }
            }
        } catch { Log-Err "blobs`t$($r.WorkTree)`t$($_.Exception.Message)" }
    }
    Write-Host "    tracked blobs exported (joins to GitHub inventory)" -ForegroundColor Green
}

# ------------------------------------------------------------- 4. PROJECTS ----

Write-Host "[4/6] Project markers..." -ForegroundColor Yellow
$markers = 'setup.py','pyproject.toml','requirements.txt','pytest.ini','tox.ini','Pipfile',
           'package.json','tsconfig.json','Dockerfile','docker-compose.yml',
           'CLAUDE.md','README.md','.env','.env.example','Makefile','*.sln','*.csproj'
$proj = foreach ($m in $markers) {
    Get-ChildItem -LiteralPath $Root -Recurse -File -Force -Filter $m -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '[\\/](\.git|node_modules|__pycache__|\.venv|venv|site-packages)[\\/]' } |
        ForEach-Object {
            [pscustomobject]@{
                Marker = $m; Directory = $_.DirectoryName; FullPath = $_.FullName
                SizeBytes = $_.Length; LastWriteUtc = $_.LastWriteTimeUtc.ToString('o')
            }
        }
}
$proj | Export-Csv -LiteralPath (Join-Path $OutDir 'project_markers.csv') -NoTypeInformation -Encoding UTF8
Write-Host ("    {0} project markers" -f @($proj).Count) -ForegroundColor Green

# ------------------------------------------------------ 5. SQLITE DATABASES ---

Write-Host "[5/6] SQLite databases (header sniff + schema if possible)..." -ForegroundColor Yellow
$sqliteHits = Import-Csv -LiteralPath $filesCsv |
    Where-Object { $_.Category -eq 'DATABASE' -or $_.Extension -in $DB_EXT }
$sqlite = foreach ($h in $sqliteHits) {
    $isSqlite = $false; $tables = ''
    try {
        $fs = [System.IO.File]::Open($h.FullPath, 'Open', 'Read', 'ReadWrite')
        try {
            $buf = New-Object byte[] 16
            [void]$fs.Read($buf, 0, 16)
            $isSqlite = ([System.Text.Encoding]::ASCII.GetString($buf, 0, 15) -eq 'SQLite format 3')
        } finally { $fs.Dispose() }
    } catch { Log-Err "sqlite`t$($h.FullPath)`t$($_.Exception.Message)" }
    if ($isSqlite -and (Get-Command sqlite3 -ErrorAction SilentlyContinue)) {
        try { $tables = ((& sqlite3 $h.FullPath '.tables' 2>$null) -join ' ').Trim() } catch { }
    }
    [pscustomobject]@{
        FullPath = $h.FullPath; SizeBytes = $h.SizeBytes; LastWriteUtc = $h.LastWriteUtc
        IsSqlite = $isSqlite; Tables = $tables; Sha256 = $h.Sha256
    }
}
$sqlite | Export-Csv -LiteralPath (Join-Path $OutDir 'sqlite_databases.csv') -NoTypeInformation -Encoding UTF8
Write-Host ("    {0} candidate databases" -f @($sqlite).Count) -ForegroundColor Green

# -------------------------------------------------------------- 6. SUMMARY ----

Write-Host "[6/6] Summary..." -ForegroundColor Yellow
$all = Import-Csv -LiteralPath $filesCsv
$sum = @()
$sum += "D:\ FORENSIC INVENTORY - COLLECTION SUMMARY"
$sum += "Collected : $(Get-Date -Format o)"
$sum += "Machine   : $env:COMPUTERNAME   User: $env:USERNAME"
$sum += "Root      : $Root"
$sum += "git       : $(if($hasGit){(& git --version)}else{'NOT ON PATH'})"
$sum += ""
$sum += "Files              : {0:N0}  (+{1:N0} .git internals excluded)" -f @($all).Count, $skippedGit
$sum += "Total bytes        : {0:N0} ({1:N1} GB)" -f $bytes, ($bytes/1GB)
$sum += "Directories        : {0:N0}" -f @($dirs).Count
$sum += "Git working trees  : {0:N0}" -f @($repos).Count
$sum += "Project markers    : {0:N0}" -f @($proj).Count
$sum += "SQLite candidates  : {0:N0}" -f @($sqlite | Where-Object IsSqlite).Count
$sum += ""
$sum += "BY CATEGORY:"
$all | Group-Object Category | Sort-Object Count -Descending | ForEach-Object {
    $sum += ("  {0,-10} {1,8:N0}" -f $_.Name, $_.Count)
}
$sum += ""
$sum += "TOP-LEVEL FOLDERS OF $Root :"
Get-ChildItem -LiteralPath $Root -Directory -Force -ErrorAction SilentlyContinue | ForEach-Object {
    $sum += ("  {0}" -f $_.Name)
}
$sum += ""
$sum += "NEWEST 40 FILES (candidate 'newer than GitHub'):"
$analysable = $all | Where-Object { $_.InGitRepo -ne 'GITINTERNAL' }
$analysable | Sort-Object LastWriteUtc -Descending | Select-Object -First 40 | ForEach-Object {
    $sum += ("  {0}  {1}" -f $_.LastWriteUtc, $_.RelPath)
}
$sum += ""
$sum += "DUPLICATE CONTENT (same git blob sha1, >1 copy) - TOP 40 BY COPY COUNT:"
$analysable | Where-Object { $_.GitBlobSha1 -and $_.GitBlobSha1 -notin @('ERROR','SKIPPED-LARGE') } |
    Group-Object GitBlobSha1 | Where-Object Count -gt 1 |
    Sort-Object Count -Descending | Select-Object -First 40 | ForEach-Object {
        $sum += ("  x{0,-4} {1}" -f $_.Count, $_.Group[0].RelPath)
    }
$sum | Set-Content -LiteralPath (Join-Path $OutDir 'SUMMARY.txt') -Encoding UTF8
$sum | Write-Host

if (-not (Test-Path $errLog)) { 'no errors' | Set-Content -LiteralPath $errLog -Encoding UTF8 }

# --------------------------------------------------------------- PACKAGE -----

$zip = "$OutDir.zip"
try {
    Compress-Archive -Path (Join-Path $OutDir '*') -DestinationPath $zip -Force
    Write-Host ""
    Write-Host "EVIDENCE PACKAGE: $zip" -ForegroundColor Cyan
    Write-Host ("  {0:N1} MB" -f ((Get-Item $zip).Length/1MB)) -ForegroundColor Cyan
} catch { Write-Warning "Zip failed: $($_.Exception.Message). Raw evidence is in $OutDir" }

Write-Host ""
Write-Host "READ-ONLY collection complete. Nothing on $Root was modified." -ForegroundColor Green
