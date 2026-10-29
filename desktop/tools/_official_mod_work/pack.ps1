# 将 unpack_out 打成与官方一致的 V11 + Oodle mod pak
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tools = Split-Path -Parent $Here
$Staging = Join-Path $Here 'unpack_out'
$OutPak = Join-Path $Here 'pakchunk0-Windows_SUTKOfficials_P.pak'
$env:EPIC_GAMES_OODLE_PATH = Join-Path $Tools 'oo2core_9_win64.dll'
$Repak = Join-Path $Tools 'repak.exe'
$Seed = [Convert]::ToInt64('66007FFB', 16)

if (-not (Test-Path $Staging)) { throw "缺少 $Staging，请先运行 extract.ps1" }

if (Test-Path $OutPak) { Remove-Item $OutPak -Force }

& $Repak pack $Staging $OutPak --version V11 --compression Oodle -p $Seed -v
& $Repak info $OutPak
Write-Host "`n完成: $OutPak"
Write-Host "复制到游戏 ProjectA\Content\Paks\ 后启动游戏验证。"
