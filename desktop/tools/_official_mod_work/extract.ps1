# 从本机 Steam Demo 主 pak 解出官职 mod 相关 7 个文件
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tools = Split-Path -Parent $Here
$MainPak = 'D:\Program Files (x86)\Steam\steamapps\common\Seres Universalis Three Kingdoms Demo\Seres Universalis Three Kingdoms Demo\ProjectA\Content\Paks\pakchunk0-Windows.pak'
$Out = Join-Path $Here 'unpack_out'
$env:EPIC_GAMES_OODLE_PATH = Join-Path $Tools 'oo2core_9_win64.dll'
$Repak = Join-Path $Tools 'repak.exe'

if (-not (Test-Path $MainPak)) { throw "未找到 MainPak: $MainPak" }

$includes = @(
  'ProjectA/Content/DataTable/Generate/Common/DT_Official.uasset',
  'ProjectA/Content/DataTable/Generate/Common/DT_Official.uexp',
  'ProjectA/Content/DataTableModify/Generate/Common/DT_Official.uasset',
  'ProjectA/Content/DataTableModify/Generate/Common/DT_Official.uexp',
  'ProjectA/Content/Localization/Game/zh-CN/Game.locres',
  'ProjectA/Content/UI/Game/Faction/BP_OfficePanel.uasset',
  'ProjectA/Content/UI/Game/Faction/BP_OfficePanel.uexp'
)

if (Test-Path $Out) { Remove-Item $Out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

$args = @('unpack', $MainPak, '-o', $Out, '-f', '-q')
foreach ($i in $includes) { $args += @('-i', $i) }
& $Repak @args

Get-ChildItem $Out -Recurse -File | ForEach-Object { Write-Host ("{0,10}  {1}" -f $_.Length, $_.FullName.Substring($Out.Length)) }
Write-Host "`n解包完成: $Out"
