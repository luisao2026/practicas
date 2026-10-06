# Sistema de Gestión de Prácticas Preprofesionales – ISTAM

Sistema web en **Python + Django** para gestionar las prácticas preprofesionales:
convenios, solicitudes, planes, informes finales, cartas de aceptación y los 3 certificados.

## 1. Requisitos
- **Python 3.11 o superior**: https://www.python.org/downloads/ (al instalar marque *"Add Python to PATH"*)
- **Visual Studio Code** con las extensiones **Python** y **Django** (VS Code las sugiere al abrir la carpeta)

## 2. Instalación (Windows, en la terminal de VS Code: *Terminal → New Terminal*)
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py cargar_demo
python manage.py runserver
```
Abra **http://127.0.0.1:8000** en el navegador.

> Si PowerShell no deja activar el entorno, ejecute una vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
> En Mac/Linux use `python3` y `source venv/bin/activate`.
> También puede iniciar con **F5** en VS Code (configuración "Django: runserver").

## 3. Usuarios de prueba
Se ingresa con la **cédula**. Contraseña de todos los usuarios de prueba: `istam2026`

| Cédula | Rol |
|---|---|
| 0900000001 | Administrador (todas las funciones + panel `/admin`) |
| 0911111110 | Rector |
| 0922222229 | Docente-coordinador |
| 0933333338 / 0944444447 | Docente-tutor |
| 0913131314 / 0924242423 / 0935353532 | Tutor empresarial (TecnoSoluciones / GAD Milagro / Contadores) |
| 0955555552 / 0910101013 / 0930303037 | Estudiante |

### Registro de usuarios
- La **cédula** es el usuario. Se valida que sea una cédula ecuatoriana correcta.
- La **contraseña inicial es la misma cédula**. En el primer ingreso el sistema obliga a cambiarla.
- **Carga masiva**: *Administración → Carga masiva*. Descargue la plantilla Excel, llénela y súbala.
  También acepta CSV. Las filas con errores se informan y las ya existentes se omiten (o se actualizan si marca la opción).
- El **tutor empresarial** se registra desde el formulario del convenio (Coordinador → Convenios), desde Usuarios, o en la carga masiva con rol `TUTOR_EMP`, el RUC de la empresa y su cargo.
- Para crear otro administrador por consola: `python manage.py createsuperuser` y escriba la cédula como *Username*.

## 4. Flujo del sistema
1. **Estudiante** ve los convenios de su carrera y crea su solicitud (puede modificarla o eliminarla mientras esté pendiente o devuelta).
2. **Coordinador** aprueba, rechaza o devuelve la solicitud y asigna al docente-tutor. Al aprobar se genera la solicitud de carta de aceptación.
3. **Rector** genera la solicitud de carta, la firma, sube el PDF firmado y la **envía por correo al tutor empresarial** del convenio.
4. **Tutor empresarial** ve la solicitud en el sistema y **genera la carta de aceptación** (o indica que no acepta). La carta llega por correo al **Rector** y al **estudiante**.
5. Con la carta aceptada, el **estudiante** llena su **plan de prácticas (Formato FPP06)**: datos prellenados y cronograma por días con clics. El **docente-tutor** lo comenta, acepta o rechaza. El plan se descarga en PDF con el formato oficial; una vez aprobado, el estudiante sube la versión firmada.
6. **Estudiante** sube su **informe final**; el **tutor** lo acepta, lo rechaza o pide correcciones (el estudiante corrige y se crea una nueva versión).
7. **Estudiante** carga el **certificado de culminación emitido por la empresa** (PDF).
8. **Tutor empresarial** llena la **evaluación del desempeño (Formato FPP08)** en el sistema. Se imprime, la firman el
   tutor empresarial y el estudiante, y el **estudiante sube el documento firmado**.
9. **Docente-tutor** genera el **Certificado de aprobación** de la práctica (requiere informe aprobado y FPP08 firmado).
10. **Coordinador** genera el **Certificado de culminación** de la práctica (requiere los pasos 7 y 9).
11. Cuando el estudiante culmina todas sus prácticas (2 por defecto, configurable por carrera), el **Rector** emite el **Certificado final**, que sirve para la aptitud legal de graduación.

Cada certificado tiene un código único que cualquiera puede validar en **/verificar/**.

## 5. Estructura del proyecto
```
config/            Configuración (settings.py, urls.py)
practicas/
  models.py        Tablas de la base de datos
  views.py         Lógica de cada pantalla, organizada por rol
  forms.py         Formularios
  urls.py          Rutas
  pdf.py           Generación de la carta y los certificados en PDF
  permisos.py      Control de acceso por rol
  tests.py         Prueba automática del flujo completo
  management/commands/cargar_demo.py   Datos de prueba
templates/         Pantallas HTML (Bootstrap 5)
static/            CSS y Bootstrap (funciona sin internet)
media/             Archivos subidos (se crea solo)
```

## 6. Configuración opcional (archivo `.env`)
Copie `.env.example` como `.env`.
- **Correo real con Gmail**: active la verificación en 2 pasos en su cuenta de Google, cree una
  *contraseña de aplicación* y colóquela en `EMAIL_HOST_PASSWORD`. Sin esto, los correos se muestran en la terminal.
- **MySQL (XAMPP)**: cree la base `practicas_istam` en phpMyAdmin, ejecute `pip install mysqlclient`
  y ponga `DB_ENGINE=mysql` en `.env`. Luego `python manage.py migrate` y `python manage.py cargar_demo`.
- **Nombre y ciudad** que salen en los PDF: `INSTITUCION_NOMBRE`, `INSTITUCION_CIUDAD` e `INSTITUCION_UBICACION`.
- **Logo**: `static/img/logo_istam.png` (horizontal, usado en la web, cartas y certificados) y `static/img/logo_icono.png` (hoja, usado en los formatos FPP).

## 7. Publicar en un servidor (VPS)
- **Con Docker + Apache** (recomendado para el VPS del ISTAM): [`deploy/GUIA_DOCKER_APACHE.md`](deploy/GUIA_DOCKER_APACHE.md)
- Sin Docker (Nginx + Gunicorn + PostgreSQL): [`deploy/GUIA_VPS.md`](deploy/GUIA_VPS.md)

## 8. Comandos útiles
```bash
python manage.py test practicas      # ejecuta la prueba del flujo completo
python manage.py createsuperuser     # crea otro administrador
python manage.py makemigrations      # después de modificar models.py
python manage.py migrate
```
