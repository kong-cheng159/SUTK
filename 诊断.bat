@echo off
chcp 936 >nul
cd /d "%~dp0"
title SUTK 修改器 . 一键诊断
setlocal
set "OUT=%~dp0诊断结果.txt"
set "PYTHONIOENCODING=gbk"

> "%OUT%" echo SUTK 修改器 诊断报告
>>"%OUT%" echo 时间: %date% %time%
>>"%OUT%" echo 目录: %~dp0

set "PY="
set "PYW="
if exist "%~dp0python\python.exe"  set "PY=%~dp0python\python.exe"
if exist "%~dp0python\pythonw.exe" set "PYW=%~dp0python\pythonw.exe"
if not defined PY  if exist "C:\Users\xr\.workbuddy\binaries\python\versions\3.13.12\python.exe"  set "PY=C:\Users\xr\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not defined PYW if exist "C:\Users\xr\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe" set "PYW=C:\Users\xr\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"

>>"%OUT%" echo.
>>"%OUT%" echo [1] 环境
if defined PY  ( >>"%OUT%" echo     python  : %PY% ) else ( >>"%OUT%" echo     [X] 找不到 python.exe )
if defined PYW ( >>"%OUT%" echo     pythonw : %PYW% ) else ( >>"%OUT%" echo     [X] 找不到 pythonw.exe )
for %%f in (SUTKMod.pyw launcher.cmd) do (
  if exist "%%f" ( >>"%OUT%" echo     [OK] %%f ) else ( >>"%OUT%" echo     [X]  缺少 %%f )
)
if exist "控制台.bat" ( >>"%OUT%" echo     [OK] 控制台.bat ) else ( >>"%OUT%" echo     [X]  缺少 控制台.bat )
if not defined PY goto :SHOW

>>"%OUT%" echo.
>>"%OUT%" echo [2] 程序自检
"%PY%" "%~dp0SUTKMod.pyw" --diagnose --nogui >>"%OUT%" 2>&1
if errorlevel 1 ( >>"%OUT%" echo     [X] 自检命令失败，见上方输出 ) else ( >>"%OUT%" echo     [OK] 程序可正常执行 )

>>"%OUT%" echo.
>>"%OUT%" echo [3] 后台热键进程
tasklist /FI "IMAGENAME eq pythonw.exe" /FO CSV /NH 2>nul | findstr /i pythonw >nul
if errorlevel 1 (
  >>"%OUT%" echo     [i] 当前没有后台进程（还没启动，属正常）
) else (
  >>"%OUT%" echo     [OK] 后台正在运行:
  tasklist /FI "IMAGENAME eq pythonw.exe" /FO CSV /NH >>"%OUT%" 2>&1
)

>>"%OUT%" echo.
>>"%OUT%" echo [4] 尝试启动后台（观察 6 秒）
if not defined PYW goto :SKIP4
del /q "%~dp0watch_err.log" 2>nul
start "" "%PYW%" "%~dp0SUTKMod.pyw" --watch
ping -n 7 127.0.0.1 >nul
tasklist /FI "IMAGENAME eq pythonw.exe" /FO CSV /NH 2>nul | findstr /i pythonw >nul
if errorlevel 1 (
  >>"%OUT%" echo     [X] 后台没能启动（热键会无效）
) else (
  >>"%OUT%" echo     [OK] 后台已运行，热键 Ctrl+Alt+F9 可用
)
if exist "%~dp0watch_err.log" (
  >>"%OUT%" echo     --- watch_err.log ---
  type "%~dp0watch_err.log" >>"%OUT%" 2>&1
)
:SKIP4

>>"%OUT%" echo.
>>"%OUT%" echo [5] 最近 12 行日志
"%PY%" -c "import io,sys;b=open(r'%~dp0mod.log','rb').read().decode('utf-8','replace').splitlines()[-12:];print(chr(10).join(b))" >>"%OUT%" 2>&1

>>"%OUT%" echo.
>>"%OUT%" echo [6] 崩溃 / 异常记录
"%PY%" -c "import io;t=open(r'%~dp0mod.log','rb').read().decode('utf-8','replace');h=[l for l in t.splitlines() if ('CRASHED' in l or 'Traceback' in l or 'run_all FAILED' in l or 'launch failed' in l)];print(chr(10).join(h[-8:]) if h else '     [OK] 没有崩溃记录')" >>"%OUT%" 2>&1

:SHOW
>>"%OUT%" echo.
>>"%OUT%" echo ---- 报告结束 ----
cls
type "%OUT%"
echo.
echo ------------------------------------------------------------
echo  报告已保存:  %OUT%
echo  把上面内容（或这个文件）发给开发者即可定位问题。
echo.
echo  备用启动方式（不依赖任何快捷方式）:
echo    直接双击本目录的「控制台.bat」
echo ------------------------------------------------------------
pause
exit /b 0