$ErrorActionPreference = 'Stop'
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
if (Test-Path -LiteralPath $dest) {
    Remove-Item -LiteralPath $dest -Recurse -Force
}
New-Item -ItemType Directory -Path $dest | Out-Null
Copy-Item -LiteralPath $exeSrc -Destination (Join-Path $dest ($name + '.exe'))
foreach ($fn in @('SUTKMod.pyw', 'MemScan.py')) {
    Copy-Item -LiteralPath (Join-Path $repo $fn) -Destination $dest
}
$guideName = -join @([char]0x7ECF, [char]0x9A8C, [char]0x603B, [char]0x7ED3) + '.md'
$guide = Join-Path $repo $guideName
if (-not (Test-Path -LiteralPath $guide)) { throw "missing $guide" }
Copy-Item -LiteralPath $guide -Destination $dest
$desk = Join-Path $dest 'desktop'
New-Item -ItemType Directory -Path $desk | Out-Null
Copy-Item -LiteralPath (Join-Path $repo 'desktop\server.py') -Destination $desk
foreach ($extra in @('names_zh.json', 'cities_zh.json', 'troop_kinds_zh.json')) {
    $src = Join-Path $repo (Join-Path 'desktop' $extra)
    if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination $desk }
}
Copy-Item -LiteralPath (Join-Path $repo 'desktop\static') -Destination $desk -Recurse
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
