@echo off
echo Creando entorno virtual...
python -m venv venv
call venv\Scripts\activate.bat
echo Instalando desde wheels locales (carpeta wheels)...
pip install --no-index --find-links=wheels -r requirements.txt
echo Instalación completada.
pause