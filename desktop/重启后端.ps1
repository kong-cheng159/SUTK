# 结束占用 8765 的界面服务，并启动 desktop\server.py
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir
if (-not (Test-Path (Join-Path $root 'python\python.exe'))) {
    $root = $scriptDir
}
$py = Join-Path $root 'python\python.exe'
$script = Join-Path $scriptDir 'server.py'
$port = 8765

if (-not (Test-Path -LiteralPath $py)) { throw "找不到 $py" }
if (-not (Test-Path -LiteralPath $script)) { throw "找不到 $script" }

function Stop-PortListeners([int]$Port) {
    for ($i = 0; $i -lt 8; $i++) {
        $pids = @()
        try {
            $pids = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
                ForEach-Object { $_.OwningProcess } | Sort-Object -Unique
        } catch { }
        if (-not $pids -or $pids.Count -eq 0) {
            $line = netstat -ano | Select-String ":$Port\s" | Select-String 'LISTENING'
            foreach ($m in $line) {
                $tok = ($m -split '\s+') | Where-Object { $_ -match '^\d+$' }
                if ($tok) { $pids += [int]$tok[-1] }
            }
            $pids = $pids | Sort-Object -Unique
        }
        if (-not $pids -or $pids.Count -eq 0) { return }
        foreach ($pid in $pids) {
            if ($pid -le 0) { continue }
            taskkill /F /PID $pid 2>$null | Out-Null
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 400
    }
}

Stop-PortListeners $port
Start-Sleep -Milliseconds 300

Start-Process -FilePath $py -ArgumentList @($script, '--no-browser', '--port', "$port") -WorkingDirectory $root -WindowStyle Hidden
Write-Host "已启动 API http://127.0.0.1:$port/ （请先不要开修改器；看到本窗口提示后再启动 SUTK修改器.exe）"
