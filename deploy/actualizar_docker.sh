#!/bin/bash
# Actualiza el sistema con lo último de GitHub (versión Docker).
# Uso: cd /opt/practicas_istam && bash deploy/actualizar_docker.sh
set -e
cd "$(dirname "$0")/.."
echo ">> Descargando cambios de GitHub..."
git pull
echo ">> Reconstruyendo y reiniciando el contenedor..."
docker compose up -d --build
docker image prune -f >/dev/null
echo ">> Estado:"
docker compose ps
echo "✔ Listo."
