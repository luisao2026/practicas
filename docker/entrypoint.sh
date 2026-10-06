#!/bin/sh
# Prepara la base de datos y los archivos estáticos antes de iniciar el sistema.
set -e

if [ "$DB_ENGINE" = "postgres" ]; then
  echo ">> Esperando a la base de datos ($DB_HOST:$DB_PORT)..."
  python - <<'PY'
import os, socket, time
host, port = os.environ.get("DB_HOST", "db"), int(os.environ.get("DB_PORT", "5432"))
for _ in range(60):
    try:
        socket.create_connection((host, port), timeout=2).close()
        break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit("No se pudo conectar a la base de datos")
PY
fi

echo ">> Aplicando migraciones..."
python manage.py migrate --noinput
echo ">> Copiando archivos estáticos..."
python manage.py collectstatic --noinput -v0
echo ">> Iniciando el sistema"
exec "$@"
