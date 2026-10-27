@echo off
chcp 936 >nul
cd /d "%~dp0"
title SUTK 修改器 - 卸载
echo.
echo  即将：还原全部存档 + 删除桌面图标 + 清除开机启动
echo.
set /p "OK=确认卸载请输入 Y 回车（直接回车取消）: "
if /i not "%OK%"=="Y" (
  echo 已取消
  timeout /t 2 >nul
  exit /b 0
)
echo.
call "%~dp0launcher.cmd" --uninstall --nogui
echo.
echo  卸载完成。本文件夹可以直接删除。
echo.
pause
