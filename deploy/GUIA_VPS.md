# Guía para instalar el sistema en un VPS (Ubuntu 22.04 / 24.04)

Arquitectura: **Nginx** (recibe las visitas, HTTPS) → **Gunicorn** (ejecuta Django) → **PostgreSQL** (base de datos).

Reemplace en toda la guía:
- `IP_DEL_SERVIDOR` → la IP pública de su VPS.
- `practicas.su-dominio.edu.ec` → su dominio o subdominio (si aún no tiene, use la IP).
- `luisao2026/practicas_istam` → su repositorio.

---

## 1. Entrar al servidor
Desde la terminal de Windows (PowerShell) o VS Code:
```bash
ssh root@IP_DEL_SERVIDOR
```

## 2. Instalar los programas necesarios
```bash
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip git nginx postgresql ufw
python3 --version     # debe ser 3.10 o superior
```

## 3. Firewall
```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

## 4. Crear el usuario del sistema
```bash
adduser --disabled-password --gecos "" practicas
usermod -aG www-data practicas
# Permitir que reinicie el servicio sin pedir contraseña (para actualizar.sh)
echo "practicas ALL=NOPASSWD: /usr/bin/systemctl restart practicas" > /etc/sudoers.d/practicas
```

## 5. Crear la base de datos
```bash
sudo -u postgres psql -c "CREATE USER practicas WITH PASSWORD 'CAMBIE_ESTA_CLAVE';"
sudo -u postgres psql -c "CREATE DATABASE practicas_istam OWNER practicas ENCODING 'UTF8';"
```

## 6. Descargar el proyecto desde GitHub
El repositorio es **privado**, así que se necesita un token:
1. En GitHub: **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
   - Repository access: **Only select repositories** → `practicas_istam`.
   - Permissions → **Contents: Read-only**.
   - Copie el token (`github_pat_...`).
2. En el servidor:
```bash
su - practicas
git clone https://luisao2026:PEGUE_EL_TOKEN@github.com/luisao2026/practicas_istam.git
cd practicas_istam
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 7. Configurar el archivo `.env`
```bash
cp deploy/env.produccion.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # copie el resultado
nano .env
```
Complete: `SECRET_KEY` (lo que copió), `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DB_PASSWORD` (la del paso 5) y el correo.
> Mientras **no** tenga HTTPS (paso 11), ponga `USAR_HTTPS=False` y en `CSRF_TRUSTED_ORIGINS` use `http://`.

Guardar en nano: **Ctrl + O**, Enter, **Ctrl + X**.

## 8. Preparar la base de datos y el administrador
```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser     # en "Username" escriba la CÉDULA del administrador
mkdir -p media
exit                                 # vuelve a root
```
> **No** ejecute `cargar_demo` en producción: crea usuarios de prueba con contraseña conocida.

Permisos para que Nginx pueda leer estáticos y archivos subidos:
```bash
chmod 750 /home/practicas
chgrp www-data /home/practicas
```

## 9. Gunicorn como servicio (se inicia solo al encender el servidor)
```bash
cp /home/practicas/practicas_istam/deploy/gunicorn.service /etc/systemd/system/practicas.service
systemctl daemon-reload
systemctl enable --now practicas
systemctl status practicas        # debe decir "active (running)"
```

## 10. Nginx
```bash
cp /home/practicas/practicas_istam/deploy/nginx.conf /etc/nginx/sites-available/practicas
nano /etc/nginx/sites-available/practicas      # cambie server_name por su dominio o IP
ln -s /etc/nginx/sites-available/practicas /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```
Ya puede abrir `http://SU_DOMINIO_O_IP` en el navegador.

## 11. HTTPS gratuito con Let's Encrypt (requiere dominio apuntando a la IP)
En el DNS del dominio cree un registro **A**: `practicas` → `IP_DEL_SERVIDOR`. Luego:
```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d practicas.su-dominio.edu.ec --redirect -m su_correo@istam.edu.ec --agree-tos
```
Después edite `/home/practicas/practicas_istam/.env`: `USAR_HTTPS=True` y `CSRF_TRUSTED_ORIGINS=https://practicas.su-dominio.edu.ec`, y reinicie:
```bash
systemctl restart practicas
```
El certificado se renueva solo.

## 12. Respaldos automáticos (recomendado)
```bash
su - practicas
crontab -e
# agregue esta línea al final (respaldo diario a las 2:00 a. m.):
0 2 * * * bash /home/practicas/practicas_istam/deploy/respaldo.sh
```
Los respaldos quedan en `/home/practicas/respaldos` (se guardan 15 días). Descárguelos de vez en cuando a otro lugar.

---

## Actualizar el sistema cuando haya cambios
1. En su computadora: Commit + **Sync** en VS Code (sube a GitHub).
2. En el servidor:
```bash
ssh root@IP_DEL_SERVIDOR
su - practicas
cd practicas_istam
bash deploy/actualizar.sh
```

## Si algo falla
| Problema | Revisar |
|---|---|
| Error 502 Bad Gateway | `journalctl -u practicas -n 50` (errores de Django/Gunicorn) |
| Error 400 Bad Request | Falta el dominio/IP en `ALLOWED_HOSTS` del `.env` |
| Error 403 CSRF al iniciar sesión | `CSRF_TRUSTED_ORIGINS` debe tener la dirección exacta con `http://` o `https://` |
| La página sale sin estilos | `python manage.py collectstatic` y permisos del paso 8 |
| No se pueden subir PDF grandes | `client_max_body_size` en la configuración de Nginx |
| No llegan los correos | Datos de Gmail en `.env` (contraseña de aplicación) |

Después de cambiar el `.env` siempre ejecute: `systemctl restart practicas`.
