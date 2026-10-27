@echo off
if exist "%~dp0python\python.exe" (
  "%~dp0python\python.exe" "%~dp0SUTKMod.pyw" %*
) else (
  "C:\Users\xr\.workbuddy\binaries\python\versions\3.13.12\python.exe" "%~dp0SUTKMod.pyw" %*
)
