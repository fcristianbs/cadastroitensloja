@echo off
chcp 65001 > nul
title VOXEL LAB · Painel Administrativo de Produtos

echo ======================================================================
echo    VOXEL LAB · Painel Administrativo de Cadastro de Produtos
echo ======================================================================
echo Iniciando ambiente e servidor local...
echo.

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    py run.py
    goto end
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python run.py
    goto end
)

echo [ERRO] Python ou inicializador 'py' não foi encontrado no sistema!
echo Por favor, instale o Python 3.10+ ou adicione-o ao PATH do Windows.
echo.
pause

:end

