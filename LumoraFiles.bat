@echo off
rem LumoraFiles: cift tiklayinca masaustu penceresini acar.
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" goto paketler

rem Python'u bul: once "py" baslaticisi, sonra "python".
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY (
    echo Python bulunamadi.
    echo python.org adresinden Python'u kur. Kurulumun ilk ekraninda
    echo "Add python.exe to PATH" kutusunu isaretlemeyi unutma.
    echo Kurulum bitince bu dosyaya tekrar cift tikla.
    start "" https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Ilk calistirma: kurulum yapiliyor...
%PY% -m venv venv || goto hata

:paketler
rem Paketler zaten kuruluysa bu satir birkac saniyede biter, internet gerekmez.
venv\Scripts\python -m pip install -q -r requirements.txt || goto hata
start "" venv\Scripts\pythonw.exe masaustu.py
exit /b 0

:hata
echo Kurulum basarisiz oldu. Bu pencerenin ekran goruntusunu gonder.
pause
exit /b 1
