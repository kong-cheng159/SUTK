# 浏览器联调：先起 Python API（8765），再起 Vite（5173）
$ErrorActionPreference = 'Stop'
$webDir = $PSScriptRoot
$root = (Resolve-Path (Join-Path $webDir '..\..')).Path
$py = Join-Path $root 'python\python.exe'
$server = Join-Path $root 'desktop\server.py'

if (-not (Test-Path $py)) {
  Write-Error "找不到 $py，请在便携版根目录运行此脚本。"
}

$port = 8765
$probe = Test-NetConnection -ComputerName 127.0.0.1 -Port $port -WarningAction SilentlyContinue
if (-not $probe.TcpTestSucceeded) {
  Write-Host "启动 API http://127.0.0.1:$port/ ..."
  Start-Process -FilePath $py -ArgumentList @($server, '--port', "$port", '--no-browser') -WorkingDirectory $root -WindowStyle Hidden
  $deadline = (Get-Date).AddSeconds(30)
  do {
    Start-Sleep -Milliseconds 400
    $probe = Test-NetConnection -ComputerName 127.0.0.1 -Port $port -WarningAction SilentlyContinue
    if ($probe.TcpTestSucceeded) { break }
  } while ((Get-Date) -lt $deadline)
  if (-not $probe.TcpTestSucceeded) {
    Write-Error "API 未在 30 秒内就绪，请查看 desktop\server.log"
  }
} else {
  Write-Host "API 已在 $port 端口运行，跳过启动。"
}

Set-Location $webDir
Write-Host "Vite: http://localhost:5173/ （/api 代理到 $port）"
npm run dev
