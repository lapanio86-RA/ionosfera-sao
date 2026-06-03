@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===========================================
echo Build - IonosferaSAO
echo ===========================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set PY=py
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set PY=python
    ) else (
        echo Python nao encontrado. Instale Python 3 para gerar o executavel.
        pause
        exit /b 1
    )
)

echo Usando Python:
%PY% --version

echo.
echo Instalando/atualizando PyInstaller...
%PY% -m pip install --upgrade pyinstaller
if %errorlevel% neq 0 (
    echo.
    echo Falha ao instalar PyInstaller.
    pause
    exit /b 1
)

echo.
echo Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist IonosferaSAO.spec del /q IonosferaSAO.spec

echo.
echo Gerando executavel...
%PY% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name IonosferaSAO ^
  ionosfera_sao_gui.py

if %errorlevel% neq 0 (
    echo.
    echo Falha no build.
    pause
    exit /b 1
)

echo.
echo ===========================================
echo Pronto!
echo Executavel gerado em:
echo   %cd%\dist\IonosferaSAO.exe
echo ===========================================
echo.
pause
