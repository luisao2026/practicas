from django.urls import path

from . import views as v

urlpatterns = [
    path("", v.inicio, name="inicio"),
    path("solicitud/<int:pk>/", v.solicitud_detalle, name="solicitud_detalle"),
    path("certificados/", v.mis_certificados, name="mis_certificados"),
    path("certificado/<int:pk>/pdf/", v.certificado_descargar, name="certificado_descargar"),
    path("verificar/", v.verificar_certificado, name="verificar"),

    # Estudiante
    path("estudiante/convenios/", v.est_convenios, name="est_convenios"),
    path("estudiante/solicitudes/", v.est_solicitudes, name="est_solicitudes"),
    path("estudiante/solicitudes/nueva/", v.est_solicitud_form, name="est_solicitud_nueva"),
    path("estudiante/solicitudes/nueva/<int:convenio_id>/", v.est_solicitud_form, name="est_solicitud_convenio"),
    path("estudiante/solicitudes/<int:pk>/editar/", v.est_solicitud_form, name="est_solicitud_editar"),
    path("estudiante/solicitudes/<int:pk>/eliminar/", v.est_solicitud_eliminar, name="est_solicitud_eliminar"),
    path("estudiante/solicitudes/<int:solicitud_id>/plan/", v.est_plan_form, name="est_plan"),
    path("estudiante/solicitudes/<int:solicitud_id>/plan/firmado/", v.est_plan_firmado, name="est_plan_firmado"),
    path("plan/<int:solicitud_id>/fpp06.pdf", v.plan_pdf, name="plan_pdf"),
    path("estudiante/solicitudes/<int:solicitud_id>/plan/eliminar/", v.est_plan_eliminar, name="est_plan_eliminar"),
    path("estudiante/solicitudes/<int:solicitud_id>/informe/", v.est_informe_form, name="est_informe"),
    path("estudiante/solicitudes/<int:solicitud_id>/informe/eliminar/", v.est_informe_eliminar,
         name="est_informe_eliminar"),
    path("estudiante/solicitudes/<int:solicitud_id>/certificado-empresa/", v.est_certificado_empresa,
         name="est_cert_empresa"),

    # Docente-tutor
    path("tutor/solicitudes/", v.tut_solicitudes, name="tut_solicitudes"),
    path("tutor/planes/", v.tut_planes, name="tut_planes"),
    path("tutor/planes/<int:pk>/", v.tut_plan_revisar, name="tut_plan_revisar"),
    path("tutor/informes/", v.tut_informes, name="tut_informes"),
    path("tutor/informes/<int:pk>/", v.tut_informe_revisar, name="tut_informe_revisar"),
    path("tutor/solicitud/<int:solicitud_id>/certificado-aprobacion/", v.tut_generar_aprobacion,
         name="tut_generar_aprobacion"),

    # Docente-coordinador
    path("coordinador/empresas/", v.coo_empresas, name="coo_empresas"),
    path("coordinador/empresas/nueva/", v.coo_empresa_form, name="coo_empresa_nueva"),
    path("coordinador/empresas/<int:pk>/editar/", v.coo_empresa_form, name="coo_empresa_editar"),
    path("coordinador/empresas/<int:pk>/eliminar/", v.coo_empresa_eliminar, name="coo_empresa_eliminar"),
    path("coordinador/convenios/", v.coo_convenios, name="coo_convenios"),
    path("coordinador/convenios/nuevo/", v.coo_convenio_form, name="coo_convenio_nuevo"),
    path("coordinador/convenios/<int:pk>/editar/", v.coo_convenio_form, name="coo_convenio_editar"),
    path("coordinador/convenios/<int:pk>/eliminar/", v.coo_convenio_eliminar, name="coo_convenio_eliminar"),
    path("coordinador/convenios/<int:pk>/tutores/", v.coo_convenio_tutores, name="coo_convenio_tutores"),
    path("coordinador/tutores-carrera/", v.coo_tutores_carrera, name="coo_tutores_carrera"),
    path("coordinador/tutores-carrera/<int:pk>/", v.coo_carrera_tutores, name="coo_carrera_tutores"),
    path("coordinador/solicitudes/", v.coo_solicitudes, name="coo_solicitudes"),
    path("coordinador/solicitudes/<int:pk>/", v.coo_solicitud_revisar, name="coo_solicitud_revisar"),
    path("coordinador/culminacion/", v.coo_culminacion, name="coo_culminacion"),
    path("coordinador/culminacion/<int:solicitud_id>/generar/", v.coo_generar_culminacion,
         name="coo_generar_culminacion"),

    # Rector
    path("rector/cartas/", v.rec_cartas, name="rec_cartas"),
    path("rector/cartas/<int:pk>/pdf/", v.rec_carta_pdf, name="rec_carta_pdf"),
    path("rector/cartas/<int:pk>/firmada/", v.rec_carta_subir, name="rec_carta_subir"),
    path("rector/cartas/<int:pk>/enviar/", v.rec_carta_enviar, name="rec_carta_enviar"),
    path("rector/certificados-finales/", v.rec_finales, name="rec_finales"),
    path("rector/certificados-finales/<int:estudiante_id>/generar/", v.rec_generar_final, name="rec_generar_final"),

    # Tutor empresarial
    path("empresa/solicitudes/", v.te_solicitudes, name="te_solicitudes"),
    path("empresa/solicitudes/<int:pk>/", v.te_carta, name="te_carta"),
    path("empresa/evaluaciones/", v.te_evaluaciones, name="te_evaluaciones"),
    path("empresa/evaluaciones/<int:solicitud_id>/", v.te_evaluacion, name="te_evaluacion"),
    path("evaluacion/<int:solicitud_id>/fpp08.pdf", v.evaluacion_pdf, name="evaluacion_pdf"),
    path("evaluacion/<int:solicitud_id>/firmada.pdf", v.evaluacion_firmada_ver, name="evaluacion_firmada_ver"),
    path("estudiante/solicitudes/<int:solicitud_id>/evaluacion/", v.est_evaluacion_subir, name="est_evaluacion_subir"),
    path("carta/<int:pk>/solicitud.pdf", v.carta_solicitud_ver, name="carta_solicitud_ver"),
    path("carta/<int:pk>/aceptacion.pdf", v.carta_aceptacion_descargar, name="carta_aceptacion_descargar"),

    # Administrador
    path("administrador/usuarios/", v.adm_usuarios, name="adm_usuarios"),
    path("administrador/usuarios/nuevo/", v.adm_usuario_form, name="adm_usuario_nuevo"),
    path("administrador/usuarios/<int:pk>/editar/", v.adm_usuario_form, name="adm_usuario_editar"),
    path("administrador/carreras/", v.adm_carreras, name="adm_carreras"),
    path("administrador/carreras/nueva/", v.adm_carrera_form, name="adm_carrera_nueva"),
    path("administrador/carreras/<int:pk>/editar/", v.adm_carrera_form, name="adm_carrera_editar"),
    path("administrador/carreras/<int:pk>/eliminar/", v.adm_carrera_eliminar, name="adm_carrera_eliminar"),
    path("administrador/usuarios/carga-masiva/", v.adm_carga_masiva, name="adm_carga_masiva"),
    path("administrador/usuarios/plantilla.xlsx", v.adm_plantilla, name="adm_plantilla"),
    path("cambiar-clave/", v.cambiar_clave, name="cambiar_clave"),
]
