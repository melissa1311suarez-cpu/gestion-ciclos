@echo off
if not exist "venv\Scripts\activate.bat" (
    echo Instalando entorno virtual y dependencias...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install --no-index --find-links=wheels -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)
echo Iniciando servidor Flask...
python app.py
pause