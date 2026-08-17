@echo off
cd /d "%~dp0"

echo Iniciando servidor KAI...
start "KAI - Servidor" cmd /k venv\Scripts\python.exe -m app.main

echo Esperando a que el servidor arranque...
timeout /t 6 /nobreak >nul

echo Iniciando tunel ngrok...
start "KAI - Tunel ngrok" cmd /k ngrok http --url=upstage-suspense-deliverer.ngrok-free.dev 8000

echo.
echo Listo. URL publica: https://upstage-suspense-deliverer.ngrok-free.dev
echo Cierra las dos ventanas que se abrieron para detener todo.
pause
