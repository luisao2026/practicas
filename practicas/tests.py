"""Prueba del flujo completo.  Ejecutar:  python manage.py test practicas"""
import shutil
from io import StringIO
import tempfile
from datetime import date

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from decimal import Decimal

from .models import (ASPECTOS_FPP08, CartaAceptacion, Certificado, Convenio, EvaluacionEmpresarial,
                     InformeFinal, PlanPracticas, Solicitud, Usuario)

MEDIA = tempfile.mkdtemp()


def datos_plan(actividades=None):
    """Datos válidos del formulario FPP06."""
    import json
    if actividades is None:
        actividades = [{"actividad": "Soporte técnico <usuarios>", "dias": ["2-3", "1-1", "1-2", "99-1", "1-9"]},
                       {"actividad": "", "dias": ["1-1"]}]
    return {
        "est_direccion": "Yantzaza", "est_telefono": "0998644529", "est_email": "luis@x.com",
        "emp_razon_social": "TecnoSoluciones & Cía.", "emp_direccion": "Av. 1", "emp_ruc": "0990000001001",
        "emp_telefono": "072300262", "emp_email": "e@x.com", "ger_nombre": "Roberto", "ger_telefono": "",
        "ger_email": "", "jefe_nombre": "Paola Ruiz", "jefe_cargo": "Jefa", "jefe_email": "p@x.com",
        "areas": "Desarrollo web", "fecha_inicio": "2026-10-01", "fecha_fin": "2026-12-15",
        "resultados_aprendizaje": "Aplicar\nconocimientos", "actividades_json": json.dumps(actividades),
    }
PDF = b"%PDF-1.4\n%prueba\n"


@override_settings(MEDIA_ROOT=MEDIA, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class FlujoCompletoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", stdout=StringIO())

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def entrar(self, usuario):
        self.client.logout()
        self.assertTrue(self.client.login(username=usuario, password="istam2026"))

    def practica(self, numero, convenio):
        est = Usuario.objects.get(username="0955555552")
        # 1. Estudiante crea solicitud
        self.entrar("0955555552")
        r = self.client.post(reverse("est_solicitud_nueva"), {
            "convenio": convenio.pk, "numero_practica": numero, "area": "Sistemas",
            "fecha_inicio": "2026-10-01", "fecha_fin": "2026-12-15", "horas": 240, "motivo": "Aprender"})
        self.assertEqual(r.status_code, 302, getattr(r, "context", {}) and r.context["form"].errors)
        s = Solicitud.objects.get(estudiante=est, numero_practica=numero)

        # 2. Coordinador devuelve, estudiante corrige, coordinador aprueba
        self.entrar("0922222229")
        self.client.post(reverse("coo_solicitud_revisar", args=[s.pk]), {"accion": "DEVUELTO", "observacion": "Corrija el área"})
        s.refresh_from_db(); self.assertEqual(s.estado, "DEVUELTO")
        self.entrar("0955555552")
        self.client.post(reverse("est_solicitud_editar", args=[s.pk]), {
            "convenio": convenio.pk, "numero_practica": numero, "area": "Desarrollo web",
            "fecha_inicio": "2026-10-01", "fecha_fin": "2026-12-15", "horas": 240, "motivo": "Aprender"})
        s.refresh_from_db(); self.assertEqual(s.estado, "PENDIENTE")
        tutor = Usuario.objects.get(username="0933333338")
        self.entrar("0922222229")
        self.client.post(reverse("coo_solicitud_revisar", args=[s.pk]), {"accion": "APROBADO", "tutor": tutor.pk, "observacion": ""})
        s.refresh_from_db(); self.assertEqual(s.estado, "APROBADO"); self.assertEqual(s.tutor, tutor)
        carta = CartaAceptacion.objects.get(solicitud=s)

        # 3. Rector: carta PDF, carga firmada, envía por correo
        self.entrar("0911111110")
        r = self.client.get(reverse("rec_carta_pdf", args=[carta.pk]))
        self.assertEqual(r["Content-Type"], "application/pdf"); self.assertTrue(r.content.startswith(b"%PDF"))
        self.client.post(reverse("rec_carta_subir", args=[carta.pk]),
                         {"archivo_firmado": SimpleUploadedFile("firmada.pdf", PDF, "application/pdf")})
        # El tutor empresarial aún no ve la solicitud (no ha sido enviada)
        te = convenio.tutor_empresarial
        self.entrar(te.cedula)
        self.assertEqual(self.client.get(reverse("te_carta", args=[carta.pk])).status_code, 404)
        self.entrar("0911111110")
        mail.outbox.clear()
        self.client.post(reverse("rec_carta_enviar", args=[carta.pk]))
        carta.refresh_from_db(); self.assertEqual(carta.estado, "ENVIADA")
        enviado = mail.outbox[0]
        self.assertEqual(enviado.to, [te.email]); self.assertEqual(len(enviado.attachments), 1)
        self.assertIn(reverse("te_carta", args=[carta.pk]), enviado.body)

        # Antes de la carta de aceptación el estudiante no puede crear el plan
        self.entrar("0955555552")
        self.client.post(reverse("est_plan", args=[s.pk]), datos_plan())
        self.assertFalse(PlanPracticas.objects.filter(solicitud=s).exists())

        # 3b. Tutor empresarial ve la solicitud y genera la carta de aceptación
        self.entrar(te.cedula)
        self.assertContains(self.client.get(reverse("te_solicitudes")), s.estudiante.get_full_name())
        self.assertEqual(self.client.get(reverse("carta_solicitud_ver", args=[carta.pk])).status_code, 200)
        r = self.client.post(reverse("te_carta", args=[carta.pk]), {"decision": "ACEPTADA", "horario": ""})
        self.assertContains(r, "Indique el horario")
        mail.outbox.clear()
        self.client.post(reverse("te_carta", args=[carta.pk]),
                         {"decision": "ACEPTADA", "horario": "Lunes a viernes 08:00-13:00"})
        carta.refresh_from_db(); self.assertEqual(carta.estado, "ACEPTADA")
        rector = Usuario.objects.get(rol="RECTOR")
        self.assertEqual(set(mail.outbox[0].to), {rector.email, s.estudiante.email})
        self.assertTrue(mail.outbox[0].attachments[0][1].startswith(b"%PDF"))
        for quien in (te.cedula, "0911111110", "0955555552"):
            self.entrar(quien)
            r = self.client.get(reverse("carta_aceptacion_descargar", args=[carta.pk]))
            self.assertTrue(r.content.startswith(b"%PDF"), quien)
        # Otro estudiante no puede verla
        self.entrar("0910101013")
        self.assertEqual(self.client.get(reverse("carta_aceptacion_descargar", args=[carta.pk])).status_code, 404)

        # 4. Plan: estudiante crea, tutor rechaza, estudiante modifica, tutor aprueba
        self.entrar("0955555552")
        # El formulario llega prellenado con datos del convenio
        r = self.client.get(reverse("est_plan", args=[s.pk]))
        self.assertContains(r, convenio.empresa.nombre)
        self.assertEqual(r.context["form"].initial["jefe_nombre"], te.get_full_name())
        # Sin actividades marcadas no se acepta
        r = self.client.post(reverse("est_plan", args=[s.pk]), datos_plan(actividades=[{"actividad": "X", "dias": []}]))
        self.assertContains(r, "Marque en el cronograma")
        plan_datos = datos_plan()
        self.client.post(reverse("est_plan", args=[s.pk]), plan_datos)
        plan = PlanPracticas.objects.get(solicitud=s)
        self.entrar("0933333338")
        self.client.post(reverse("tut_plan_revisar", args=[plan.pk]), {"accion": "RECHAZADO", "texto": "Detalle el cronograma"})
        plan.refresh_from_db(); self.assertEqual(plan.estado, "RECHAZADO")
        self.entrar("0955555552")
        self.client.post(reverse("est_plan", args=[s.pk]), {**plan_datos, "areas": "Desarrollo web y soporte"})
        self.entrar("0933333338")
        self.client.post(reverse("tut_plan_revisar", args=[plan.pk]), {"accion": "APROBADO", "texto": ""})
        plan.refresh_from_db(); self.assertEqual(plan.estado, "APROBADO")
        self.assertEqual(plan.areas, "Desarrollo web y soporte")
        self.assertEqual(plan.actividades[0]["dias"], ["1-1", "1-2", "2-3"])
        # PDF FPP06 y subida del plan firmado
        self.entrar("0955555552")
        self.assertTrue(self.client.get(reverse("plan_pdf", args=[s.pk])).content.startswith(b"%PDF"))
        self.client.post(reverse("est_plan_firmado", args=[s.pk]),
                         {"archivo": SimpleUploadedFile("fpp06.pdf", PDF, "application/pdf")})
        plan.refresh_from_db(); self.assertTrue(plan.archivo)

        # 5. Informe: correcciones y aprobación
        self.entrar("0955555552")
        inf_datos = {"resumen": "R", "actividades_realizadas": "A", "resultados": "Re", "conclusiones": "C", "horas_cumplidas": 240}
        self.client.post(reverse("est_informe", args=[s.pk]), inf_datos)
        inf = InformeFinal.objects.get(solicitud=s)
        self.entrar("0933333338")
        self.client.post(reverse("tut_informe_revisar", args=[inf.pk]), {"accion": "CORRECCION", "texto": "Agregue evidencias"})
        inf.refresh_from_db(); self.assertEqual(inf.estado, "CORRECCION")
        self.entrar("0955555552")
        self.client.post(reverse("est_informe", args=[s.pk]), {**inf_datos, "resumen": "R corregido"})
        inf.refresh_from_db(); self.assertEqual((inf.estado, inf.version), ("PENDIENTE", 2))
        self.assertFalse(inf.observaciones.filter(atendida=False).exists())
        self.entrar("0933333338")
        self.client.post(reverse("tut_informe_revisar", args=[inf.pk]), {"accion": "APROBADO", "texto": ""})

        # Sin evaluación FPP08 firmada no se genera el certificado de aprobación
        self.client.post(reverse("tut_generar_aprobacion", args=[s.pk]))
        self.assertFalse(Certificado.objects.filter(solicitud=s, tipo="APROBACION").exists())

        # 5b. Tutor empresarial registra la evaluación FPP08
        self.entrar(te.cedula)
        notas = {c: "0.9" for c, _, _ in ASPECTOS_FPP08}
        r = self.client.post(reverse("te_evaluacion", args=[s.pk]), {**notas, "tec_1": "1.5"})
        self.assertFalse(EvaluacionEmpresarial.objects.filter(solicitud=s).exists())
        self.client.post(reverse("te_evaluacion", args=[s.pk]), {**notas, "tec_1": "1", "soc_4": "0.6"})
        ev = EvaluacionEmpresarial.objects.get(solicitud=s)
        self.assertEqual(ev.nota_final, Decimal("8.800"))
        self.assertEqual(ev.subtotales["EXCELENTE"], Decimal("1"))
        self.assertEqual(ev.subtotales["REGULAR"], Decimal("0.6"))
        self.assertTrue(self.client.get(reverse("evaluacion_pdf", args=[s.pk])).content.startswith(b"%PDF"))
        # El estudiante descarga, imprime, firma y sube
        self.entrar("0955555552")
        self.assertTrue(self.client.get(reverse("evaluacion_pdf", args=[s.pk])).content.startswith(b"%PDF"))
        self.client.post(reverse("est_evaluacion_subir", args=[s.pk]),
                         {"archivo_firmado": SimpleUploadedFile("fpp08.pdf", PDF, "application/pdf")})
        ev.refresh_from_db(); self.assertTrue(ev.archivo_firmado)
        # Ya firmada, el tutor empresarial no puede cambiarla
        self.entrar(te.cedula)
        self.client.post(reverse("te_evaluacion", args=[s.pk]), {**notas})
        ev.refresh_from_db(); self.assertEqual(ev.nota_final, Decimal("8.800"))

        # 6. Tutor genera certificado de aprobación
        self.entrar("0933333338")
        self.client.post(reverse("tut_generar_aprobacion", args=[s.pk]))
        self.assertTrue(Certificado.objects.filter(solicitud=s, tipo="APROBACION").exists())

        # 7. Coordinador no puede generar culminación sin certificado de la empresa
        self.entrar("0922222229")
        self.client.post(reverse("coo_generar_culminacion", args=[s.pk]))
        self.assertFalse(Certificado.objects.filter(solicitud=s, tipo="CULMINACION").exists())
        self.entrar("0955555552")
        self.client.post(reverse("est_cert_empresa", args=[s.pk]),
                         {"certificado_empresa": SimpleUploadedFile("empresa.pdf", PDF, "application/pdf")})
        self.entrar("0922222229")
        self.client.post(reverse("coo_generar_culminacion", args=[s.pk]))
        self.assertTrue(Certificado.objects.filter(solicitud=s, tipo="CULMINACION").exists())
        return s

    def test_flujo_dos_practicas_y_certificado_final(self):
        c1 = Convenio.objects.get(codigo="CONV-2025-001")
        c2 = Convenio.objects.get(codigo="CONV-2025-002")
        self.practica(1, c1)

        # Con una sola práctica el Rector aún no puede emitir el certificado final
        est = Usuario.objects.get(username="0955555552")
        self.entrar("0911111110")
        self.client.post(reverse("rec_generar_final", args=[est.pk]))
        self.assertFalse(Certificado.objects.filter(estudiante=est, tipo="FINAL").exists())

        self.practica(2, c2)
        self.entrar("0911111110")
        self.client.post(reverse("rec_generar_final", args=[est.pk]))
        final = Certificado.objects.get(estudiante=est, tipo="FINAL")

        # Todos los PDF se generan
        self.entrar("0955555552")
        for c in Certificado.objects.filter(estudiante=est):
            r = self.client.get(reverse("certificado_descargar", args=[c.pk]))
            self.assertTrue(r.content.startswith(b"%PDF"), c.tipo)
        # Verificación pública
        self.client.logout()
        r = self.client.get(reverse("verificar"), {"codigo": final.codigo})
        self.assertContains(r, "Certificado válido")

    def test_permisos_y_paginas(self):
        paginas = {
            "0955555552": ["est_convenios", "est_solicitudes", "est_solicitud_nueva", "mis_certificados"],
            "0933333338": ["tut_solicitudes", "tut_planes", "tut_informes"],
            "0922222229": ["coo_empresas", "coo_empresa_nueva", "coo_convenios", "coo_convenio_nuevo",
                            "coo_tutores_carrera", "coo_solicitudes", "coo_culminacion"],
            "0911111110": ["rec_cartas", "rec_finales"],
            "0913131314": ["te_solicitudes", "te_evaluaciones"],
        }
        todas = [p for lista in paginas.values() for p in lista] + ["adm_usuarios", "adm_usuario_nuevo"]
        for usuario, lista in paginas.items():
            self.entrar(usuario)
            self.assertEqual(self.client.get(reverse("inicio")).status_code, 200)
            for p in lista:
                self.assertEqual(self.client.get(reverse(p)).status_code, 200, f"{usuario} {p}")
            # No puede entrar a secciones de otros roles
            ajena = next(p for p in todas if p not in lista and not p.startswith("mis_"))
            self.assertEqual(self.client.get(reverse(ajena)).status_code, 302, f"{usuario} -> {ajena}")
        # El administrador accede a todo
        self.entrar("0900000001")
        for p in todas:
            self.assertEqual(self.client.get(reverse(p)).status_code, 200, f"admin {p}")

    def test_estudiante_no_ve_solicitudes_ajenas(self):
        c1 = Convenio.objects.get(codigo="CONV-2025-001")
        otro = Usuario.objects.get(username="0910101013")
        s = Solicitud.objects.create(estudiante=otro, convenio=c1, area="X", fecha_inicio=date(2026, 1, 1),
                                     fecha_fin=date(2026, 3, 1), motivo="m")
        self.entrar("0955555552")
        self.assertEqual(self.client.get(reverse("solicitud_detalle", args=[s.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("est_solicitud_editar", args=[s.pk])).status_code, 404)


@override_settings(MEDIA_ROOT=MEDIA)
class UsuariosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", stdout=StringIO())

    def setUp(self):
        self.client.login(username="0900000001", password="istam2026")

    def test_validar_cedula(self):
        from .validadores import cedula_valida
        self.assertTrue(cedula_valida("0912345675"))
        self.assertFalse(cedula_valida("0912345678"))
        self.assertFalse(cedula_valida("12345"))

    def test_crear_usuario_y_primer_ingreso(self):
        from .models import Carrera
        r = self.client.post(reverse("adm_usuario_nuevo"), {
            "cedula": "0912345675", "first_name": "Juan", "last_name": "Pérez", "email": "j@x.com",
            "rol": "ESTUDIANTE", "carrera": Carrera.objects.first().pk})
        self.assertEqual(r.status_code, 302)
        u = Usuario.objects.get(cedula="0912345675")
        self.assertEqual(u.username, "0912345675")
        self.assertTrue(u.debe_cambiar_clave)
        # cédula repetida o inválida
        r = self.client.post(reverse("adm_usuario_nuevo"), {
            "cedula": "0912345675", "first_name": "X", "last_name": "Y", "email": "y@x.com", "rol": "TUTOR"})
        self.assertContains(r, "Ya existe un usuario con esta cédula")
        r = self.client.post(reverse("adm_usuario_nuevo"), {
            "cedula": "0912345678", "first_name": "X", "last_name": "Y", "email": "y@x.com", "rol": "TUTOR"})
        self.assertContains(r, "no es válida")
        # Primer ingreso: con la cédula como contraseña, obliga a cambiarla
        self.client.logout()
        self.assertTrue(self.client.login(username="0912345675", password="0912345675"))
        r = self.client.get(reverse("est_solicitudes"))
        self.assertRedirects(r, reverse("cambiar_clave"))
        self.client.post(reverse("cambiar_clave"), {
            "old_password": "0912345675", "new_password1": "NuevaClave2026", "new_password2": "NuevaClave2026"})
        u.refresh_from_db()
        self.assertFalse(u.debe_cambiar_clave)
        self.assertEqual(self.client.get(reverse("est_solicitudes")).status_code, 200)

    def test_plantilla_y_carga_masiva(self):
        from openpyxl import load_workbook
        from io import BytesIO
        r = self.client.get(reverse("adm_plantilla"))
        self.assertEqual(r.status_code, 200)
        wb = load_workbook(BytesIO(r.content))
        ws = wb["Usuarios"]
        ws.delete_rows(2)
        filas = [
            ["0912345675", "juan carlos", "pérez lópez", "juan@x.com", "0991234567", "Estudiante", "TDS"],
            [912345675, "Repetido", "En archivo", "r@x.com", "", "ESTUDIANTE", "TDS"],  # sin el 0 y repetido
            ["0920202025", "Rosa", "Vera", "rosa@x.com", "", "Docente-Tutor", ""],
            ["0912345678", "Mala", "Cedula", "m@x.com", "", "ESTUDIANTE", "TDS"],
            ["0940404049", "Sin", "Carrera", "s@x.com", "", "ESTUDIANTE", ""],
            ["0930303037", "Kevin", "Morán", "kevin@x.com", "", "ESTUDIANTE", "TCO"],  # ya existe
            ["", "", "", "", "", "", ""],
        ]
        for f in filas:
            ws.append(f)
        buf = BytesIO(); wb.save(buf)
        archivo = SimpleUploadedFile("usuarios.xlsx", buf.getvalue())
        r = self.client.post(reverse("adm_carga_masiva"), {"archivo": archivo})
        res = r.context["resultado"]
        self.assertEqual((res["creados"], res["omitidos"], res["errores"]), (2, 1, 3), res["filas"])
        juan = Usuario.objects.get(cedula="0912345675")
        self.assertEqual((juan.first_name, juan.rol, juan.carrera.codigo), ("Juan Carlos", "ESTUDIANTE", "TDS"))
        self.assertTrue(juan.check_password("0912345675"))
        self.assertEqual(Usuario.objects.get(cedula="0920202025").rol, "TUTOR")

        # CSV con punto y coma y actualización
        csv = "CÉDULA;NOMBRES;APELLIDOS;CORREO;TELÉFONO;ROL;CARRERA (código)\n0930303037;Kevin;Morán;nuevo@x.com;;ESTUDIANTE;TCO\n"
        r = self.client.post(reverse("adm_carga_masiva"), {
            "archivo": SimpleUploadedFile("u.csv", csv.encode("utf-8")), "actualizar": "on"})
        self.assertEqual(r.context["resultado"]["actualizados"], 1)
        self.assertEqual(Usuario.objects.get(cedula="0930303037").email, "nuevo@x.com")
        self.assertTrue(Usuario.objects.get(cedula="0930303037").check_password("istam2026"))


class CarrerasTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", stdout=StringIO())

    def test_crud_carreras(self):
        from .models import Carrera
        self.client.login(username="0900000001", password="istam2026")
        self.assertContains(self.client.get(reverse("adm_carreras")), "TDS")
        self.client.post(reverse("adm_carrera_nueva"), {"codigo": " enf2 ", "nombre": "Enfermería 2",
                                                        "practicas_requeridas": 3, "horas_por_practica": 200})
        c = Carrera.objects.get(codigo="ENF2")
        self.assertContains(self.client.get(reverse("adm_carga_masiva")), "ENF2")
        # Con usuarios no se puede eliminar; vacía sí
        tds = Carrera.objects.get(codigo="TDS")
        self.client.post(reverse("adm_carrera_eliminar", args=[tds.pk]))
        self.assertTrue(Carrera.objects.filter(pk=tds.pk).exists())
        self.client.post(reverse("adm_carrera_eliminar", args=[c.pk]))
        self.assertFalse(Carrera.objects.filter(pk=c.pk).exists())
        # Un coordinador no puede entrar
        self.client.login(username="0922222229", password="istam2026")
        self.assertEqual(self.client.get(reverse("adm_carreras")).status_code, 302)



@override_settings(MEDIA_ROOT=MEDIA, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class TutorEmpresarialTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", stdout=StringIO())

    def test_empresa_no_acepta(self):
        from .models import CartaAceptacion
        est = Usuario.objects.get(cedula="0955555552")
        conv = Convenio.objects.get(codigo="CONV-2025-001")
        s = Solicitud.objects.create(estudiante=est, convenio=conv, area="X", fecha_inicio=date(2026, 1, 1),
                                     fecha_fin=date(2026, 3, 1), motivo="m", estado="APROBADO")
        carta = CartaAceptacion.objects.create(solicitud=s, numero="T-1", estado="ENVIADA")
        # Tutor empresarial de otra empresa no la ve
        self.client.login(username="0924242423", password="istam2026")
        self.assertEqual(self.client.get(reverse("te_carta", args=[carta.pk])).status_code, 404)
        self.client.login(username="0913131314", password="istam2026")
        r = self.client.post(reverse("te_carta", args=[carta.pk]), {"decision": "NO_ACEPTADA"})
        self.assertContains(r, "Indique el motivo")
        self.client.post(reverse("te_carta", args=[carta.pk]),
                         {"decision": "NO_ACEPTADA", "observacion_empresa": "Sin cupos este período"})
        carta.refresh_from_db(); s.refresh_from_db()
        self.assertEqual((carta.estado, s.estado), ("NO_ACEPTADA", "RECHAZADO"))
        self.assertTrue(any(est.email in m.to for m in mail.outbox))

    def test_convenio_registra_tutor_empresarial(self):
        from .models import Carrera, Empresa
        self.client.login(username="0922222229", password="istam2026")
        datos = {"codigo": "CONV-NEW", "empresa": Empresa.objects.first().pk,
                 "carreras": [Carrera.objects.first().pk], "cupos": 3, "fecha_inicio": "2026-01-01",
                 "fecha_fin": "2027-01-01", "activo": "on", "rep_legal_nombre": "Rep"}
        r = self.client.post(reverse("coo_convenio_nuevo"), datos)
        self.assertContains(r, "Seleccione un tutor empresarial")
        r = self.client.post(reverse("coo_convenio_nuevo"), {**datos, "te_cedula": "0921212122", "te_nombres": "rosa",
                                                             "te_apellidos": "mora", "te_correo": "rosa@x.com",
                                                             "te_cargo": "Jefa"})
        self.assertEqual(r.status_code, 302)
        conv = Convenio.objects.get(codigo="CONV-NEW")
        te = conv.tutor_empresarial
        self.assertEqual((te.rol, te.first_name, te.empresa, te.cargo), ("TUTOR_EMP", "Rosa", conv.empresa, "Jefa"))
        self.assertTrue(te.check_password("0921212122"))


@override_settings(MEDIA_ROOT=MEDIA)
class ArchivosProtegidosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_demo", stdout=StringIO())

    def test_solo_usuarios_con_permiso_descargan(self):
        est = Usuario.objects.get(cedula="0955555552")
        conv = Convenio.objects.get(codigo="CONV-2025-001")
        s = Solicitud.objects.create(estudiante=est, convenio=conv, area="X", fecha_inicio=date(2026, 1, 1),
                                     fecha_fin=date(2026, 3, 1), motivo="m", estado="APROBADO",
                                     tutor=Usuario.objects.get(cedula="0933333338"))
        plan = PlanPracticas.objects.create(solicitud=s, est_direccion="d", est_telefono="1", est_email="a@b.c",
                                            emp_razon_social="E", emp_direccion="D", ger_nombre="G",
                                            jefe_nombre="J", areas="A", fecha_inicio=date(2026, 1, 5),
                                            fecha_fin=date(2026, 3, 1), resultados_aprendizaje="R")
        plan.archivo.save("plan.pdf", SimpleUploadedFile("plan.pdf", PDF), save=True)
        url = "/media/" + plan.archivo.name
        # Sin sesión: redirige al login
        self.assertEqual(self.client.get(url).status_code, 302)
        # Dueño, su docente-tutor y el coordinador: sí
        for ced in ("0955555552", "0933333338", "0922222229"):
            self.client.login(username=ced, password="istam2026")
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, ced)
            self.assertEqual(b"".join(r.streaming_content), PDF)
        # Otro estudiante o un tutor empresarial de otra empresa: no
        for ced in ("0910101013", "0924242423"):
            self.client.login(username=ced, password="istam2026")
            self.assertEqual(self.client.get(url).status_code, 404, ced)
        # Rutas maliciosas
        self.client.login(username="0955555552", password="istam2026")
        self.assertEqual(self.client.get("/media/../config/settings.py").status_code, 404)
