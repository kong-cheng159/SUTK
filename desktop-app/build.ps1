$ErrorActionPreference = 'Stop'

function Stop-ProcessesUnder([string]$root) {
    if (-not (Test-Path -LiteralPath $root)) { return }
    try { $root = (Resolve-Path -LiteralPath $root).Path } catch { return }
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object {
        $exe = $_.ExecutablePath
        if ($exe -and $exe.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Prepare-DistDirectory([string]$dest) {
    if (-not (Test-Path -LiteralPath $dest)) {
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
        return
    }
    Stop-ProcessesUnder $dest
    Start-Sleep -Milliseconds 800
    $removed = $false
    foreach ($try in 1..3) {
        try {
            Remove-Item -LiteralPath $dest -Recurse -Force -ErrorAction Stop
            $removed = $true
            break
        } catch {
            if ($try -lt 3) { Start-Sleep -Milliseconds 700 }
        }
    }
    if (-not $removed) {
        $parent = Split-Path $dest -Parent
        $leaf = Split-Path $dest -Leaf
        $archName = $leaf + '._old_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
        $arch = Join-Path $parent $archName
        try {
            Rename-Item -LiteralPath $dest -NewName $archName -ErrorAction Stop
            Write-Warning "Could not delete dist (files locked). Renamed to $archName — close SUTK modifier / python from that folder and delete manually."
        } catch {
            throw "dist is locked ($dest). Close SUTK修改器.exe and any python from dist, then run build.ps1 again."
        }
    }
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
}

$app = $PSScriptRoot
$repo = Split-Path $app -Parent
$web = Join-Path $repo 'desktop\web'
if (Test-Path -LiteralPath (Join-Path $web 'package.json')) {
    Push-Location $web
    try {
        if (-not (Test-Path -LiteralPath 'node_modules')) { npm install }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'npm run build failed' }
    } finally { Pop-Location }
}
$name = 'SUTK' + [char]0x4FEE + [char]0x6539 + [char]0x5668
$dest = Join-Path $app (Join-Path 'dist' $name)
$exeSrc = Join-Path $app 'src-tauri\target\release\sutk-mod.exe'
if (-not (Test-Path -LiteralPath $exeSrc)) {
    throw "missing exe: $exeSrc"
}
Prepare-DistDirectory $dest
Copy-Item -LiteralPath $exeSrc -Destination (Join-Path $dest ($name + '.exe'))
foreach ($fn in @('SUTKMod.pyw', 'MemScan.py')) {
    Copy-Item -LiteralPath (Join-Path $repo $fn) -Destination $dest
}
function Copy-RepoDoc([string]$name) {
    $candidates = @(
        (Join-Path $repo (Join-Path 'docs' $name)),
        (Join-Path $repo $name)
    )
    foreach ($docPath in $candidates) {
        if (Test-Path -LiteralPath $docPath) {
            Copy-Item -LiteralPath $docPath -Destination $dest
            return
        }
    }
    if ($name -ne 'README.md') { throw "missing doc: $name" }
}
$docJingyan = [char]0x7ECF + [char]0x9A8C + [char]0x603B + [char]0x7ED3 + '.md'
$docDesktop = [char]0x684C + [char]0x9762 + [char]0x7248 + [char]0x4F7F + [char]0x7528 + [char]0x8BF4 + [char]0x660E + '.md'
$docConsole = [char]0x4F7F + [char]0x7528 + [char]0x8BF4 + [char]0x660E + '.md'
Copy-RepoDoc $docJingyan
foreach ($doc in @($docDesktop, 'README.md', $docConsole)) { Copy-RepoDoc $doc }
$desk = Join-Path $dest 'desktop'
New-Item -ItemType Directory -Path $desk | Out-Null
Copy-Item -LiteralPath (Join-Path $repo 'desktop\server.py') -Destination $desk
foreach ($extra in @(
        'names_zh.json', 'cities_zh.json', 'troop_kinds_zh.json',
        'officials_han_staffing.json', 'game_titles_zh.json'
    )) {
    $src = Join-Path $repo (Join-Path 'desktop' $extra)
    if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination $desk }
}
Copy-Item -LiteralPath (Join-Path $repo 'desktop\static') -Destination $desk -Recurse
$dataSrc = Join-Path $repo 'desktop\data'
if (Test-Path -LiteralPath $dataSrc) {
    Copy-Item -LiteralPath $dataSrc -Destination (Join-Path $desk 'data') -Recurse
}
$restartName = [char]0x91CD + [char]0x542F + [char]0x540E + [char]0x7AEF + '.ps1'
$restartPs1 = Join-Path $repo (Join-Path 'desktop' $restartName)
if (Test-Path -LiteralPath $restartPs1) {
    Copy-Item -LiteralPath $restartPs1 -Destination $desk
    @(
        '@echo off',
        'chcp 65001 >nul',
        'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0desktop\重启后端.ps1"',
        'pause'
    ) | Set-Content -LiteralPath (Join-Path $dest ($restartName -replace '\.ps1$', '.bat')) -Encoding UTF8
}
$index = Join-Path $desk 'static\index.html'
if (-not (Test-Path -LiteralPath $index)) { throw "missing $index" }
$pyDest = Join-Path $dest 'python'
& robocopy (Join-Path $repo 'python') $pyDest /E /XD __pycache__ /XF *.pyc *.pyo /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed: $LASTEXITCODE" }
$note = Get-ChildItem -LiteralPath $app -File | Where-Object { $_.Extension -eq '.txt' } | Select-Object -First 1
if ($note) { Copy-Item -LiteralPath $note.FullName -Destination $dest }
$py = Join-Path $pyDest 'python.exe'
$pyw = Join-Path $pyDest 'pythonw.exe'
if (-not (Test-Path -LiteralPath $py)) { throw "missing $py" }
if (-not (Test-Path -LiteralPath $pyw)) { throw "missing $pyw" }
Write-Output "OK $dest"
