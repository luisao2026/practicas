# Instalar el sistema en el VPS con Docker + Apache

**Dominio:** `practicaspre.istam.edu.ec` · **Servidor web:** Apache (el mismo de Moodle `eva.istam.edu.ec`)

```
Internet ──► Apache (80/443) ──┬──► eva.istam.edu.ec ........ Moodle (no se toca)
                               └──► practicaspre.istam.edu.ec ─► 127.0.0.1:8081 ─► contenedor practicas_web
                                                                                      └─► contenedor practicas_db (PostgreSQL)
```
El sistema corre en sus **propios contenedores**, con su propia base de datos. No comparte nada con Moodle.

---

## Paso 0. Crear el subdominio (DNS)
En el panel donde administran el dominio `istam.edu.ec`, cree un registro:

| Tipo | Nombre | Valor |
|---|---|---|
| A | `practicaspre` | IP pública del VPS (la misma de `eva`) |

Compruebe desde su PC (puede tardar unos minutos): `ping practicaspre.istam.edu.ec`

## Paso 1. Entrar al servidor y revisar
```bash
ssh root@IP_DEL_VPS
docker --version
docker compose version        # debe responder (Compose v2)
ss -ltnp | grep 8081          # NO debe mostrar nada (puerto libre)
```
> Si el 8081 ya está ocupado, use otro (ej. 8082) en `PUERTO` del `.env` (paso 3) y en la configuración de Apache (paso 6).

## Paso 2. Descargar el proyecto desde GitHub
El repositorio es privado: cree un token de **solo lectura**.
1. GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**
   - *Repository access*: **Only select repositories** → `practicas_istam`
   - *Permissions* → **Contents: Read-only**
2. En el servidor:
```bash
cd /opt
git clone https://luisao2026:PEGUE_EL_TOKEN@github.com/luisao2026/practicas_istam.git
cd practicas_istam
```

## Paso 3. Configurar el archivo `.env`
```bash
cp deploy/env.docker.example .env
openssl rand -base64 48        # copie el resultado: será la SECRET_KEY
nano .env
```
Cambie como mínimo:
- `SECRET_KEY` → lo que generó arriba.
- `DB_PASSWORD` → una contraseña fuerte para la base de datos.
- Datos del correo (`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`), si ya los tiene.
- **Mientras no tenga HTTPS (paso 7)**: `USAR_HTTPS=False` y `CSRF_TRUSTED_ORIGINS=http://practicaspre.istam.edu.ec`

Guardar: **Ctrl + O**, Enter, **Ctrl + X**.
```bash
chmod 600 .env
```

## Paso 4. Construir y levantar los contenedores
```bash
docker compose up -d --build
docker compose ps                         # practicas_web y practicas_db deben estar "Up" / "healthy"
docker compose logs -f web                # Ctrl + C para salir; debe decir "Iniciando el sistema"
curl -I -H "Host: practicaspre.istam.edu.ec" http://127.0.0.1:8081/login/    # debe responder 200 OK
```

## Paso 5. Crear el administrador
```bash
docker compose exec web python manage.py createsuperuser
```
En **Username** escriba la **cédula** del administrador. Luego se ingresa con esa cédula.
> **No** ejecute `cargar_demo` en el servidor (crea usuarios de prueba con contraseña conocida).

## Paso 6. Publicar el sitio en Apache
```bash
a2enmod proxy proxy_http headers
cp deploy/apache-practicaspre.conf /etc/apache2/sites-available/practicaspre.istam.edu.ec.conf
a2ensite practicaspre.istam.edu.ec
apache2ctl configtest            # debe decir "Syntax OK"
systemctl reload apache2
```
Abra **http://practicaspre.istam.edu.ec** → debe aparecer la pantalla de inicio de sesión.
Verifique también que **eva.istam.edu.ec** siga funcionando normal.

## Paso 7. HTTPS (certificado gratuito)
Si Moodle ya tiene certificado, Certbot ya está instalado. Si no: `apt install -y certbot python3-certbot-apache`
```bash
certbot --apache -d practicaspre.istam.edu.ec --redirect
```
Luego active HTTPS en el sistema:
```bash
nano .env      # USAR_HTTPS=True   y   CSRF_TRUSTED_ORIGINS=https://practicaspre.istam.edu.ec
docker compose up -d
```
Listo: **https://practicaspre.istam.edu.ec**

## Paso 8. Respaldos automáticos (recomendado)
```bash
crontab -e
# agregue al final (todos los días a las 2:00 a. m.):
0 2 * * * bash /opt/practicas_istam/deploy/respaldo_docker.sh >> /var/log/respaldo_practicas.log 2>&1
```
Los respaldos quedan en `/opt/respaldos/practicas` (se guardan 15 días).

---

## Actualizar el sistema cuando haya cambios
1. En su PC: **Commit** y **Sync** en VS Code.
2. En el servidor:
```bash
cd /opt/practicas_istam
bash deploy/actualizar_docker.sh
```
(Descarga de GitHub, reconstruye la imagen, aplica migraciones y reinicia. Los datos y archivos subidos se conservan.)

## Comandos útiles
| Para… | Comando (dentro de `/opt/practicas_istam`) |
|---|---|
| Ver si está corriendo | `docker compose ps` |
| Ver errores | `docker compose logs --tail 100 web` |
| Reiniciar | `docker compose restart web` |
| Detener / iniciar | `docker compose down` / `docker compose up -d` |
| Consola de Django | `docker compose exec web python manage.py shell` |
| Restaurar un respaldo de la BD | `gunzip -c /opt/respaldos/practicas/bd_FECHA.sql.gz \| docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'` |

> **Cuidado:** `docker compose down -v` **borra la base de datos y los archivos subidos**. Use solo `docker compose down`.

## Si algo falla
| Problema | Solución |
|---|---|
| **503 Service Unavailable** (Apache) | El contenedor no está corriendo: `docker compose ps` y `docker compose logs web` |
| **400 Bad Request** | Falta el dominio en `ALLOWED_HOSTS` del `.env` → `docker compose up -d` |
| **403 CSRF** al iniciar sesión | `CSRF_TRUSTED_ORIGINS` debe ser exactamente `https://practicaspre.istam.edu.ec` (o `http://` si aún no hay HTTPS) |
| Bucle de redirecciones o no guarda la sesión | `USAR_HTTPS=True` solo después de instalar el certificado (paso 7) |
| No se pueden subir PDF grandes | `LimitRequestBody` en el archivo de Apache |
| No llegan los correos | Revise los datos de correo en `.env` y `docker compose logs web` |
| Moodle dejó de funcionar | `apache2ctl configtest`; desactive el sitio nuevo con `a2dissite practicaspre.istam.edu.ec && systemctl reload apache2` |

Después de cambiar el `.env` siempre ejecute: `docker compose up -d`
