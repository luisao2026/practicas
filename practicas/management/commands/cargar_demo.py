"""Crea datos de demostración: carreras, usuarios de cada rol, empresas y convenios.

Uso:  python manage.py cargar_demo
Se ingresa con la cédula; todos los usuarios de prueba tienen la contraseña:  istam2026
"""
from datetime import date

from django.core.management.base import BaseCommand

from practicas.models import Carrera, Convenio, Empresa, Usuario

CLAVE = "istam2026"


class Command(BaseCommand):
    help = "Carga datos de demostración para probar el sistema."

    def handle(self, *args, **opts):
        dev, _ = Carrera.objects.get_or_create(codigo="TDS", defaults={"nombre": "Desarrollo de Software"})
        cont, _ = Carrera.objects.get_or_create(codigo="TCO", defaults={"nombre": "Contabilidad"})
        enf, _ = Carrera.objects.get_or_create(codigo="TEN", defaults={"nombre": "Enfermería"})

        def usuario(cedula, nombre, apellido, rol, carrera=None, correo="", superuser=False):
            u, creado = Usuario.objects.get_or_create(username=cedula, defaults={
                "first_name": nombre, "last_name": apellido, "rol": rol, "carrera": carrera,
                "cedula": cedula, "email": correo,
                "is_staff": superuser, "is_superuser": superuser,
            })
            if creado:
                u.set_password(CLAVE)
                u.save()
            return u

        usuario("0900000001", "Administrador", "Sistema", "ADMIN", correo="admin@istam.edu.ec", superuser=True)
        usuario("0911111110", "María Elena", "Villacís", "RECTOR", correo="rector@istam.edu.ec")
        usuario("0922222229", "Carlos", "Mendoza", "COORDINADOR", dev, "coordinador@istam.edu.ec")
        t1 = usuario("0933333338", "Ana", "Paredes", "TUTOR", dev, "ana.paredes@istam.edu.ec")
        t2 = usuario("0944444447", "Jorge", "Salazar", "TUTOR", cont, "jorge.salazar@istam.edu.ec")
        usuario("0955555552", "Luis", "Pérez", "ESTUDIANTE", dev, "luis.perez@istam.edu.ec")
        usuario("0910101013", "Valeria", "Torres", "ESTUDIANTE", dev, "valeria.torres@istam.edu.ec")
        usuario("0930303037", "Kevin", "Morán", "ESTUDIANTE", cont, "kevin.moran@istam.edu.ec")
        dev.tutores.add(t1)
        cont.tutores.add(t2)

        e1, _ = Empresa.objects.get_or_create(ruc="0990000001001", defaults={
            "nombre": "TecnoSoluciones S.A.", "tipo": "PRIVADA", "direccion": "Av. 9 de Octubre 100, Guayaquil",
            "telefono": "042000001", "correo": "rrhh@tecnosoluciones.example"})
        e2, _ = Empresa.objects.get_or_create(ruc="0960000002001", defaults={
            "nombre": "GAD Municipal de Milagro", "tipo": "PUBLICA", "direccion": "Calle García Moreno, Milagro",
            "telefono": "042000002", "correo": "talentohumano@milagro.example"})
        e3, _ = Empresa.objects.get_or_create(ruc="0990000003001", defaults={
            "nombre": "Contadores Asociados Cía. Ltda.", "tipo": "PRIVADA", "direccion": "Cdla. Kennedy, Guayaquil",
            "telefono": "042000003", "correo": "info@contadores.example"})

        def convenio(codigo, empresa, carreras, tutores, **extra):
            c, creado = Convenio.objects.get_or_create(codigo=codigo, defaults={
                "empresa": empresa, "fecha_inicio": date(2025, 1, 1), "fecha_fin": date(2028, 12, 31),
                "cupos": 5, **extra})
            if creado:
                c.carreras.set(carreras)
                c.tutores.set(tutores)

        def tutor_emp(cedula, nombre, apellido, cargo, empresa, correo):
            u = usuario(cedula, nombre, apellido, "TUTOR_EMP", correo=correo)
            u.cargo, u.empresa = cargo, empresa
            u.save()
            return u

        te1 = tutor_emp("0913131314", "Paola", "Ruiz", "Jefa de Sistemas", e1, "pruiz@tecnosoluciones.example")
        te2 = tutor_emp("0924242423", "Diego", "León", "Director de TIC", e2, "dleon@milagro.example")
        te3 = tutor_emp("0935353532", "Andrés", "Gómez", "Contador Senior", e3, "agomez@contadores.example")

        convenio("CONV-2025-001", e1, [dev], [t1], objeto="Prácticas en desarrollo web y soporte técnico.",
                 rep_legal_nombre="Roberto Andrade", rep_legal_cargo="Gerente General", tutor_empresarial=te1)
        convenio("CONV-2025-002", e2, [dev, cont], [t1, t2], objeto="Prácticas en la Dirección de TIC y Financiero.",
                 rep_legal_nombre="Lcdo. Fernando Castro", rep_legal_cargo="Alcalde", tutor_empresarial=te2)
        convenio("CONV-2025-003", e3, [cont], [t2], objeto="Prácticas contables y tributarias.",
                 rep_legal_nombre="CPA Mónica Vera", rep_legal_cargo="Gerente", tutor_empresarial=te3)

        self.stdout.write(self.style.SUCCESS(
            f"Datos de demostración cargados. Ingrese con la cédula y la contraseña {CLAVE}:\n"
            "  0900000001 Administrador | 0911111110 Rector | 0922222229 Coordinador\n"
            "  0933333338 Tutor (Ana)   | 0944444447 Tutor (Jorge)\n"
            "  0913131314 Tutor empresarial (TecnoSoluciones) | 0924242423 Tutor empresarial (GAD Milagro) | "
            "0935353532 Tutor empresarial (Contadores)\n"
            "  0955555552 Estudiante (Luis) | 0910101013 Estudiante (Valeria) | 0930303037 Estudiante (Kevin)"))
