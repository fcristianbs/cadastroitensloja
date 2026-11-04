@echo off
chcp 65001 > nul
title Gerando executavel - VOXEL LAB Admin
cd /d "%~dp0"

set PY=py
where py >nul 2>nul || set PY=python

echo Instalando dependencias...
%PY% -m pip install -r requirements.txt -r requirements-build.txt || goto erro

echo Gerando executavel...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "VoxelLabAdmin" ^
  --icon "icon.ico" ^
  --add-data "app\templates;app\templates" ^
  --add-data "app\static;app\static" ^
  --add-data "icon.ico;." ^
  --hidden-import pystray._win32 ^
  tray_app.py || goto erro

if exist ".env" copy /Y ".env" "dist\.env" > nul

echo.
echo Pronto! Executavel em: dist\VoxelLabAdmin.exe
echo (o arquivo .env precisa ficar na mesma pasta do .exe)
pause
exit /b 0

:erro
echo [ERRO] Falha na geracao do executavel.
pause
exit /b 1
