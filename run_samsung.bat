@echo off
cd /d "C:\Users\GleydsonVictorOlivei\Bacnet_bot"

echo ------------------------------------------
echo     INICIANDO BOT SAMSUNG BACNET (AUTO)
echo ------------------------------------------

"C:\Users\GleydsonVictorOlivei\AppData\Local\Python\pythoncore-3.14-64\python.exe" bot.py

if %errorlevel% neq 0 (
    echo.
    echo [!] O bot parou com um erro. Verifique acima.
    pause
)
