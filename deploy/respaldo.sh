#!/bin/bash
# Respaldo diario de la base de datos y los archivos subidos.
# Programarlo con:  crontab -e   →   0 2 * * * bash /home/practicas/practicas_istam/deploy/respaldo.sh
set -e
DESTINO=/home/practicas/respaldos
FECHA=$(date +%Y-%m-%d)
mkdir -p "$DESTINO"
pg_dump practicas_istam | gzip > "$DESTINO/bd_$FECHA.sql.gz"
tar -czf "$DESTINO/media_$FECHA.tar.gz" -C /home/practicas/practicas_istam media
# Conserva solo los últimos 15 días
find "$DESTINO" -type f -mtime +15 -delete
