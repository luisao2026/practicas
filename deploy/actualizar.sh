#!/bin/bash
# Actualiza el sistema en el servidor con lo último de GitHub.
# Uso (como usuario practicas):  bash deploy/actualizar.sh
set -e
cd /home/practicas/practicas_istam
echo ">> Descargando cambios de GitHub..."
git pull
source venv/bin/activate
echo ">> Instalando dependencias..."
pip install -q -r requirements.txt
echo ">> Actualizando base de datos..."
python manage.py migrate --noinput
echo ">> Copiando archivos estáticos..."
python manage.py collectstatic --noinput -v0
echo ">> Reiniciando el sistema..."
sudo systemctl restart practicas
echo "✔ Listo."
