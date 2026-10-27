@echo off
chcp 936 >nul
cd /d "%~dp0"
title SUTK 修改器 - 安装
echo.
echo  ============================================
echo    SUTK 修改器  一键安装
echo  ============================================
echo.
call "%~dp0launcher.cmd" --setup --nogui
echo.
echo  --------------------------------------------
echo   安装完成，正在打开控制台...
echo   以后每次玩，双击桌面「SUTK 修改器」即可
echo  --------------------------------------------
echo.
call "%~dp0控制台.bat"
