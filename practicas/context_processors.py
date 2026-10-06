"""Construye el menú lateral según el rol del usuario conectado."""

MENUS = {
    "ESTUDIANTE": [
        ("Convenios disponibles", "est_convenios", "bi-building"),
        ("Mis prácticas", "est_solicitudes", "bi-journal-text"),
        ("Mis certificados", "mis_certificados", "bi-award"),
    ],
    "TUTOR": [
        ("Solicitudes asignadas", "tut_solicitudes", "bi-inbox"),
        ("Planes por revisar", "tut_planes", "bi-list-check"),
        ("Informes por revisar", "tut_informes", "bi-file-earmark-check"),
    ],
    "COORDINADOR": [
        ("Empresas", "coo_empresas", "bi-briefcase"),
        ("Convenios", "coo_convenios", "bi-building"),
        ("Tutores por carrera", "coo_tutores_carrera", "bi-people"),
        ("Solicitudes", "coo_solicitudes", "bi-inbox"),
        ("Certificados de culminación", "coo_culminacion", "bi-award"),
    ],
    "TUTOR_EMP": [
        ("Solicitudes de carta", "te_solicitudes", "bi-envelope-open"),
        ("Evaluación de estudiantes (FPP08)", "te_evaluaciones", "bi-clipboard-check"),
    ],
    "RECTOR": [
        ("Cartas de aceptación", "rec_cartas", "bi-envelope-paper"),
        ("Certificados finales", "rec_finales", "bi-mortarboard"),
    ],
}

ETIQUETAS = {
    "ESTUDIANTE": "Estudiante",
    "TUTOR": "Docente-tutor",
    "COORDINADOR": "Docente-coordinador",
    "RECTOR": "Rector",
    "TUTOR_EMP": "Tutor empresarial",
}


def menu(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    if user.es_admin:
        # El administrador ve todas las secciones agrupadas por rol
        secciones = [("Administración", [
            ("Carreras", "adm_carreras", "bi-diagram-3"),
            ("Usuarios", "adm_usuarios", "bi-person-gear"),
            ("Carga masiva", "adm_carga_masiva", "bi-file-earmark-spreadsheet"),
            ("Panel Django", "admin:index", "bi-gear"),
        ])]
        secciones += [(ETIQUETAS[r], items) for r, items in MENUS.items()]
    else:
        secciones = [(ETIQUETAS.get(user.rol, ""), MENUS.get(user.rol, []))]
    return {"menu_secciones": secciones}


def institucion(request):
    from django.conf import settings
    return {"INSTITUCION_NOMBRE": settings.INSTITUCION_NOMBRE, "INSTITUCION_UBICACION": settings.INSTITUCION_UBICACION}
