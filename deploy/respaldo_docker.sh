#!/bin/bash
# Respaldo de la base de datos y los archivos subidos (versión Docker).
# Programar:  crontab -e  →  0 2 * * * bash /opt/practicas_istam/deploy/respaldo_docker.sh
set -e
cd "$(dirname "$0")/.."
DESTINO=/opt/respaldos/practicas
FECHA=$(date +%Y-%m-%d)
mkdir -p "$DESTINO"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$DESTINO/bd_$FECHA.sql.gz"
docker compose exec -T web tar -czf - -C /app media > "$DESTINO/media_$FECHA.tar.gz"
find "$DESTINO" -type f -mtime +15 -delete
echo "Respaldo guardado en $DESTINO"
