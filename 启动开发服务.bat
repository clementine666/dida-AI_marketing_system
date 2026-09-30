@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 道旅营销协作系统 - 开发服务

echo.
echo [1/2] 释放 8000 端口（如有旧服务）...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
  taskkill /F /PID %%a >nul 2>&1
)

echo [2/2] 启动服务（改代码会自动重启）...
echo.
py -3.11 scripts\run_dev.py

echo.
pause
