"""
Configuración del Sistema de Gestión de Prácticas Preprofesionales - ISTAM.

Los valores sensibles (clave secreta, correo, base de datos) se leen de variables
de entorno o del archivo .env (ver .env.example).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Carga sencilla del archivo .env (sin dependencias externas) ---
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


def env(key, default=None):
    return os.environ.get(key, default)


DEBUG = env("DEBUG", "True") == "True"
SECRET_KEY = env("SECRET_KEY", "cambie-esta-clave-en-produccion-istam" if DEBUG else None)
if not SECRET_KEY:
    raise RuntimeError("En producción (DEBUG=False) debe definir SECRET_KEY en el archivo .env")
ALLOWED_HOSTS = [h.strip() for h in env("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
# Ej.: https://practicas.istam.edu.ec  (necesario para formularios bajo HTTPS)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# --- Seguridad en producción (detrás de Nginx con HTTPS) ---
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USAR_HTTPS = env("USAR_HTTPS", "True") == "True"
    SESSION_COOKIE_SECURE = USAR_HTTPS
    CSRF_COOKIE_SECURE = USAR_HTTPS
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "practicas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # sirve CSS/JS/imágenes en producción
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "practicas.middleware.CambioClaveObligatorioMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "practicas.context_processors.menu",
                "practicas.context_processors.institucion",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Base de datos ---
# Por defecto SQLite (no requiere instalar nada).
# Para MySQL: DB_ENGINE=mysql en .env y `pip install mysqlclient`.
if env("DB_ENGINE") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "practicas_istam"),
            "USER": env("DB_USER", "practicas"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "127.0.0.1"),
            "PORT": env("DB_PORT", "5432"),
        }
    }
elif env("DB_ENGINE") == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("DB_NAME", "practicas_istam"),
            "USER": env("DB_USER", "root"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "127.0.0.1"),
            "PORT": env("DB_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "practicas.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "es-ec"
TIME_ZONE = "America/Guayaquil"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(env("STATIC_ROOT", BASE_DIR / "staticfiles"))
if not DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
    }

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", BASE_DIR / "media"))
# Los archivos subidos (cartas, informes, evaluaciones) NO son públicos: los entrega Django
# después de verificar permisos. En el servidor, con MEDIA_X_ACCEL=True, Nginx hace el envío.
MEDIA_X_ACCEL = env("MEDIA_X_ACCEL", "False") == "True"
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "inicio"
LOGOUT_REDIRECT_URL = "login"

# --- Correo ---
# En desarrollo los correos se muestran en la terminal.
# Para enviar de verdad con Gmail, configure en .env:
#   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
#   EMAIL_HOST_USER=sucorreo@gmail.com
#   EMAIL_HOST_PASSWORD=contraseña_de_aplicación_de_google
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "practicas@istam.edu.ec")

# --- Datos institucionales usados en los PDF ---
INSTITUCION_NOMBRE = env("INSTITUCION_NOMBRE", "INSTITUTO SUPERIOR TECNOLÓGICO “AMAZÓNICO”")
INSTITUCION_CIUDAD = env("INSTITUCION_CIUDAD", "Yantzaza")
INSTITUCION_UBICACION = env("INSTITUCION_UBICACION", "Yantzaza – Zamora Chinchipe – Ecuador")
# Logos usados en los PDF (static/img): horizontal para cartas/certificados, ícono para formatos FPP
INSTITUCION_LOGO = BASE_DIR / "static" / "img" / "logo_istam.png"
INSTITUCION_LOGO_ICONO = BASE_DIR / "static" / "img" / "logo_icono.png"
