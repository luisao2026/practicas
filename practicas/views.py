import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.mail import EmailMessage, send_mail
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import permisos
from .forms import (
    ArchivoFirmadoForm, CargaMasivaForm, CarreraForm, CertificadoEmpresaForm, ConvenioForm, DecisionSolicitudForm, EmpresaForm,
    EvaluacionFirmadaForm, EvaluacionForm, InformeForm, PlanFirmadoForm, PlanForm, RespuestaCartaForm, SolicitudForm, TextoForm, TutoresForm, UsuarioForm,
)
from .models import (
    ASPECTOS_FPP08, NIVELES_FPP08, Carrera, CartaAceptacion, Certificado, ComentarioPlan, Convenio, Empresa,
    EvaluacionEmpresarial, InformeFinal,
    ObservacionInforme, PlanPracticas, Solicitud, Usuario,
)
from .carga_usuarios import generar_plantilla, procesar_archivo
from .pdf import (carta_aceptacion_empresa_pdf, certificado_pdf, evaluacion_fpp08_pdf, plan_fpp06_pdf,
                  solicitud_carta_pdf)


# ===========================================================================
# Utilidades
# ===========================================================================
def notificar(usuario, asunto, mensaje):
    """Envía un correo informativo (en desarrollo aparece en la terminal)."""
    if usuario and usuario.email:
        send_mail(f"[Prácticas ISTAM] {asunto}", mensaje, settings.DEFAULT_FROM_EMAIL,
                  [usuario.email], fail_silently=True)


def pdf_respuesta(contenido, nombre, descargar=False):
    r = HttpResponse(contenido, content_type="application/pdf")
    r["Content-Disposition"] = f'{"attachment" if descargar else "inline"}; filename="{nombre}"'
    return r


def puede_ver_solicitud(user, s):
    return (
        user.es_admin
        or user.rol in ("COORDINADOR", "RECTOR")
        or (user.rol == "ESTUDIANTE" and s.estudiante_id == user.id)
        or (user.rol == "TUTOR" and (s.tutor_id == user.id or s.convenio.tutores.filter(pk=user.pk).exists()))
        or (user.rol == "TUTOR_EMP" and s.convenio.tutor_empresarial_id == user.id)
    )


def cartas_de_tutor_emp(user):
    qs = CartaAceptacion.objects.select_related(
        "solicitud__estudiante__carrera", "solicitud__convenio__empresa", "solicitud__tutor")
    qs = qs.exclude(estado__in=["POR_FIRMAR", "FIRMADA"])  # aún no enviadas por el Rector
    return qs if user.es_admin else qs.filter(solicitud__convenio__tutor_empresarial=user)


def solicitudes_de_tutor(user):
    qs = Solicitud.objects.select_related("estudiante", "convenio__empresa")
    return qs if user.es_admin else qs.filter(tutor=user)


# ===========================================================================
# Archivos subidos protegidos
# ===========================================================================
# carpeta -> (modelo, campo, función que devuelve la solicitud)
_CARPETAS_PROTEGIDAS = {
    "planes": (PlanPracticas, "archivo", lambda o: o.solicitud),
    "informes": (InformeFinal, "archivo", lambda o: o.solicitud),
    "certificados_empresa": (InformeFinal, "certificado_empresa", lambda o: o.solicitud),
    "cartas": (CartaAceptacion, "archivo_firmado", lambda o: o.solicitud),
    "cartas_aceptacion": (CartaAceptacion, "archivo_aceptacion", lambda o: o.solicitud),
    "evaluaciones": (EvaluacionEmpresarial, "archivo_firmado", lambda o: o.solicitud),
}


@login_required
def media_protegida(request, ruta):
    """Entrega un archivo subido solo si el usuario tiene permiso sobre la práctica a la que pertenece."""
    ruta = ruta.replace("\\", "/")
    if ".." in ruta.split("/"):
        raise Http404
    carpeta = ruta.split("/", 1)[0]
    if carpeta == "convenios":
        permitido = True  # documentos de convenio: cualquier usuario autenticado
    elif carpeta in _CARPETAS_PROTEGIDAS:
        modelo, campo, solicitud_de = _CARPETAS_PROTEGIDAS[carpeta]
        obj = modelo.objects.filter(**{campo: ruta}).first()
        permitido = bool(obj) and puede_ver_solicitud(request.user, solicitud_de(obj))
    else:
        permitido = request.user.es_admin
    if not permitido:
        raise Http404
    archivo = Path(settings.MEDIA_ROOT) / ruta
    if not archivo.is_file():
        raise Http404
    if settings.MEDIA_X_ACCEL:
        r = HttpResponse()
        r["Content-Type"] = mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"
        r["X-Accel-Redirect"] = "/media-interna/" + ruta
        return r
    return FileResponse(archivo.open("rb"), as_attachment=False, filename=archivo.name)


# ===========================================================================
# Comunes
# ===========================================================================
@login_required
def inicio(request):
    u = request.user
    tarjetas = []
    if u.rol == "ESTUDIANTE":
        mias = Solicitud.objects.filter(estudiante=u)
        culm = Certificado.objects.filter(estudiante=u, tipo="CULMINACION").count()
        req = u.carrera.practicas_requeridas if u.carrera else 2
        tarjetas += [
            ("Mis solicitudes", mias.count(), "est_solicitudes", "primary"),
            ("Aprobadas", mias.filter(estado="APROBADO").count(), "est_solicitudes", "success"),
            (f"Prácticas culminadas (de {req})", culm, "mis_certificados", "warning"),
        ]
    if u.tiene_rol("TUTOR"):
        mias = solicitudes_de_tutor(u)
        tarjetas += [
            ("Prácticas en curso", mias.filter(estado="APROBADO").count(), "tut_solicitudes", "primary"),
            ("Planes por revisar", PlanPracticas.objects.filter(solicitud__in=mias, estado="PENDIENTE").count(),
             "tut_planes", "warning"),
            ("Informes por revisar", InformeFinal.objects.filter(solicitud__in=mias, estado="PENDIENTE").count(),
             "tut_informes", "danger"),
        ]
    if u.tiene_rol("COORDINADOR"):
        tarjetas += [
            ("Convenios vigentes", Convenio.objects.filter(activo=True).count(), "coo_convenios", "primary"),
            ("Solicitudes pendientes", Solicitud.objects.filter(estado="PENDIENTE").count(), "coo_solicitudes", "warning"),
            ("Culminaciones por emitir", _pendientes_culminacion().count(), "coo_culminacion", "success"),
        ]
    if u.tiene_rol("TUTOR_EMP"):
        cartas = cartas_de_tutor_emp(u)
        tarjetas += [
            ("Solicitudes de carta por responder", cartas.filter(estado="ENVIADA").count(), "te_solicitudes", "warning"),
            ("Estudiantes aceptados", cartas.filter(estado="ACEPTADA").count(), "te_evaluaciones", "success"),
            ("Evaluaciones FPP08 por registrar",
             cartas.filter(estado="ACEPTADA", solicitud__evaluacion__isnull=True).count(), "te_evaluaciones", "danger"),
        ]
    if u.tiene_rol("RECTOR"):
        tarjetas += [
            ("Cartas por firmar/enviar", CartaAceptacion.objects.filter(estado__in=["POR_FIRMAR", "FIRMADA"]).count(),
             "rec_cartas", "warning"),
            ("Estudiantes aptos sin certificado final", len(_aptos_certificado_final()), "rec_finales", "success"),
        ]
    return render(request, "inicio.html", {"tarjetas": tarjetas})


@login_required
def solicitud_detalle(request, pk):
    s = get_object_or_404(
        Solicitud.objects.select_related("estudiante__carrera", "convenio__empresa", "tutor"), pk=pk
    )
    if not puede_ver_solicitud(request.user, s):
        raise Http404
    ctx = {
        "s": s,
        "plan": getattr(s, "plan", None),
        "informe": getattr(s, "informe", None),
        "carta": getattr(s, "carta", None),
        "ev": getattr(s, "evaluacion", None),
        "certificados": s.certificados.all(),
    }
    return render(request, "solicitud_detalle.html", ctx)


@login_required
def mis_certificados(request):
    u = request.user
    certs = Certificado.objects.filter(estudiante=u).select_related("solicitud__convenio__empresa")
    req = u.carrera.practicas_requeridas if u.carrera else 2
    return render(request, "estudiante/certificados.html", {
        "certificados": certs, "requeridas": req,
        "culminadas": certs.filter(tipo="CULMINACION").count(),
    })


@login_required
def certificado_descargar(request, pk):
    c = get_object_or_404(Certificado, pk=pk)
    u = request.user
    if not (u.es_admin or u.rol in ("COORDINADOR", "RECTOR") or c.estudiante_id == u.id or c.emitido_por_id == u.id):
        raise Http404
    return pdf_respuesta(certificado_pdf(c), f"{c.codigo}.pdf")


def verificar_certificado(request):
    """Página pública para verificar la autenticidad de un certificado por su código."""
    codigo = request.GET.get("codigo", "").strip().upper()
    cert = Certificado.objects.filter(codigo=codigo).select_related("estudiante").first() if codigo else None
    return render(request, "verificar.html", {"codigo": codigo, "cert": cert})


# ===========================================================================
# ESTUDIANTE
# ===========================================================================
@permisos.estudiante
def est_convenios(request):
    u = request.user
    qs = Convenio.objects.filter(activo=True).select_related("empresa").prefetch_related("carreras")
    if u.carrera_id and not u.es_admin:
        qs = qs.filter(carreras=u.carrera)
    q = request.GET.get("q", "")
    if q:
        qs = qs.filter(Q(empresa__nombre__icontains=q) | Q(objeto__icontains=q))
    return render(request, "estudiante/convenios.html", {"convenios": qs, "q": q})


@permisos.estudiante
def est_solicitudes(request):
    qs = Solicitud.objects.filter(estudiante=request.user).select_related("convenio__empresa", "tutor")
    return render(request, "estudiante/solicitudes.html", {"solicitudes": qs})


@permisos.estudiante
def est_solicitud_form(request, pk=None, convenio_id=None):
    inst = None
    if pk:
        inst = get_object_or_404(Solicitud, pk=pk, estudiante=request.user)
        if not inst.editable:
            messages.error(request, "Solo puede modificar solicitudes pendientes o devueltas.")
            return redirect("est_solicitudes")
    form = SolicitudForm(request.POST or None, instance=inst, estudiante=request.user,
                         initial={"convenio": convenio_id} if convenio_id else None)
    if request.method == "POST" and form.is_valid():
        s = form.save(commit=False)
        s.estudiante = request.user
        if s.estado == Solicitud.Estado.DEVUELTO:
            s.estado = Solicitud.Estado.PENDIENTE  # se reenvía al coordinador
        s.save()
        messages.success(request, "Solicitud guardada y enviada al docente-coordinador.")
        return redirect("est_solicitudes")
    return render(request, "form.html", {
        "form": form, "titulo": "Editar solicitud" if pk else "Nueva solicitud de prácticas",
        "volver": "est_solicitudes", "nota": inst.observacion if inst and inst.estado == "DEVUELTO" else "",
    })


@permisos.estudiante
def est_solicitud_eliminar(request, pk):
    s = get_object_or_404(Solicitud, pk=pk, estudiante=request.user)
    if not s.editable:
        messages.error(request, "No puede eliminar una solicitud ya procesada.")
        return redirect("est_solicitudes")
    if request.method == "POST":
        s.delete()
        messages.success(request, "Solicitud eliminada.")
        return redirect("est_solicitudes")
    return render(request, "confirmar.html", {"objeto": s, "volver": "est_solicitudes"})


@permisos.estudiante
def est_plan_form(request, solicitud_id):
    s = get_object_or_404(Solicitud, pk=solicitud_id, estudiante=request.user)
    if s.estado != Solicitud.Estado.APROBADO:
        messages.error(request, "La solicitud debe estar aprobada para registrar el plan.")
        return redirect("solicitud_detalle", s.pk)
    carta = getattr(s, "carta", None)
    if not carta or not carta.aceptada:
        messages.error(request, "Podrá registrar el plan cuando el tutor empresarial emita la carta de aceptación.")
        return redirect("solicitud_detalle", s.pk)
    plan = getattr(s, "plan", None)
    if plan and not plan.editable:
        messages.info(request, "El plan ya fue aprobado y no puede modificarse.")
        return redirect("solicitud_detalle", s.pk)
    form = PlanForm(request.POST or None, instance=plan, initial=None if plan else _datos_iniciales_plan(s))
    if request.method == "POST" and form.is_valid():
        p = form.save(commit=False)
        p.solicitud = s
        p.estado = PlanPracticas.Estado.PENDIENTE
        p.save()
        notificar(s.tutor, "Plan de prácticas por revisar",
                  f"{request.user.get_full_name()} registró/actualizó su plan de prácticas (FPP06).")
        messages.success(request, "Plan guardado y enviado al docente-tutor para revisión. "
                                  "Puede descargarlo en PDF con el botón «Descargar FPP06».")
        return redirect("solicitud_detalle", s.pk)
    return render(request, "estudiante/plan_form.html", {"form": form, "s": s, "plan": plan})


def _datos_iniciales_plan(s):
    """Prellena el FPP06 con lo que el sistema ya conoce."""
    u, conv = s.estudiante, s.convenio
    emp, te = conv.empresa, conv.tutor_empresarial
    anterior = PlanPracticas.objects.filter(solicitud__estudiante=u).order_by("-creado").first()
    return {
        "est_direccion": anterior.est_direccion if anterior else "",
        "est_telefono": u.telefono or (anterior.est_telefono if anterior else ""),
        "est_email": u.email,
        "emp_razon_social": emp.nombre, "emp_direccion": emp.direccion, "emp_ruc": emp.ruc,
        "emp_telefono": emp.telefono, "emp_email": emp.correo,
        "ger_nombre": conv.rep_legal_nombre,
        "jefe_nombre": te.get_full_name() if te else "", "jefe_cargo": te.cargo if te else "",
        "jefe_email": te.email if te else "",
        "areas": s.area, "fecha_inicio": s.fecha_inicio, "fecha_fin": s.fecha_fin,
    }


@login_required
def plan_pdf(request, solicitud_id):
    s = get_object_or_404(Solicitud, pk=solicitud_id)
    plan = getattr(s, "plan", None)
    if not plan or not puede_ver_solicitud(request.user, s):
        raise Http404
    return pdf_respuesta(plan_fpp06_pdf(plan), f"FPP06_{s.estudiante.cedula}_practica{s.numero_practica}.pdf")


@permisos.estudiante
def est_plan_firmado(request, solicitud_id):
    s = get_object_or_404(Solicitud, pk=solicitud_id, estudiante=request.user)
    plan = get_object_or_404(PlanPracticas, solicitud=s)
    if plan.estado != PlanPracticas.Estado.APROBADO:
        messages.error(request, "Podrá subir el plan firmado cuando su docente-tutor lo apruebe.")
        return redirect("solicitud_detalle", s.pk)
    form = PlanFirmadoForm(request.POST or None, request.FILES or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        form.save()
        notificar(s.tutor, "Plan de prácticas firmado cargado",
                  f"{request.user.get_full_name()} subió su plan de prácticas (FPP06) firmado.")
        messages.success(request, "Plan firmado cargado correctamente.")
        return redirect("solicitud_detalle", s.pk)
    return render(request, "form.html", {
        "form": form, "titulo": "Subir plan de prácticas firmado (FPP06)", "subtitulo": str(s),
        "volver_url": s.pk, "multipart": True})


@permisos.estudiante
def est_plan_eliminar(request, solicitud_id):
    s = get_object_or_404(Solicitud, pk=solicitud_id, estudiante=request.user)
    plan = get_object_or_404(PlanPracticas, solicitud=s)
    if not plan.editable or hasattr(s, "informe"):
        messages.error(request, "Este plan ya no puede eliminarse.")
        return redirect("solicitud_detalle", s.pk)
    if request.method == "POST":
        plan.delete()
        messages.success(request, "Plan eliminado.")
        return redirect("solicitud_detalle", s.pk)
    return render(request, "confirmar.html", {"objeto": plan, "volver_url": s.pk})


@permisos.estudiante
def est_informe_form(request, solicitud_id):
    s = get_object_or_404(Solicitud, pk=solicitud_id, estudiante=request.user)
    plan = getattr(s, "plan", None)
    if not plan or plan.estado != PlanPracticas.Estado.APROBADO:
        messages.error(request, "Su plan de prácticas debe estar aprobado antes de subir el informe final.")
        return redirect("solicitud_detalle", s.pk)
    informe = getattr(s, "informe", None)
    if informe and not informe.editable:
        messages.info(request, "El informe ya fue aprobado.")
        return redirect("solicitud_detalle", s.pk)
    form = InformeForm(request.POST or None, request.FILES or None, instance=informe)
    if request.method == "POST" and form.is_valid():
        inf = form.save(commit=False)
        inf.solicitud = s
        if informe and informe.estado in (InformeFinal.Estado.CORRECCION, InformeFinal.Estado.RECHAZADO):
            inf.version += 1  # nueva versión corregida
            informe.observaciones.filter(atendida=False).update(atendida=True)
        inf.estado = InformeFinal.Estado.PENDIENTE
        inf.save()
        notificar(s.tutor, "Informe final por revisar",
                  f"{request.user.get_full_name()} envió su informe final (versión {inf.version}).")
        messages.success(request, "Informe final enviado al docente-tutor.")
        return redirect("solicitud_detalle", s.pk)
    observaciones = informe.observaciones.filter(atendida=False) if informe else []
    return render(request, "estudiante/informe_form.html", {
        "form": form, "s": s, "informe": informe, "observaciones": observaciones,
    })


@permisos.estudiante
def est_informe_eliminar(request, solicitud_id):
    s = get_object_or_404(Solicitud, pk=solicitud_id, estudiante=request.user)
    inf = get_object_or_404(InformeFinal, solicitud=s)
    if not inf.editable:
        messages.error(request, "Un informe aprobado no puede eliminarse.")
        return redirect("solicitud_detalle", s.pk)
    if request.method == "POST":
        inf.delete()
        messages.success(request, "Informe eliminado.")
        return redirect("solicitud_detalle", s.pk)
    return render(request, "confirmar.html", {"objeto": inf, "volver_url": s.pk})


@permisos.estudiante
def est_certificado_empresa(request, solicitud_id):
    """Carga del certificado de culminación emitido por la empresa (PDF)."""
    s = get_object_or_404(Solicitud, pk=solicitud_id, estudiante=request.user)
    inf = getattr(s, "informe", None)
    if not inf:
        messages.error(request, "Primero debe registrar su informe final.")
        return redirect("solicitud_detalle", s.pk)
    form = CertificadoEmpresaForm(request.POST or None, request.FILES or None, instance=inf)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Certificado de la empresa cargado correctamente.")
        return redirect("solicitud_detalle", s.pk)
    return render(request, "form.html", {
        "form": form, "titulo": "Cargar certificado de culminación de la empresa",
        "subtitulo": str(s), "volver_url": s.pk, "multipart": True,
    })


# ===========================================================================
# DOCENTE-TUTOR
# ===========================================================================
@permisos.tutor
def tut_solicitudes(request):
    u = request.user
    asignadas = solicitudes_de_tutor(u)
    # También puede visualizar las solicitudes de los convenios que tutoriza
    de_convenios = Solicitud.objects.filter(convenio__tutores=u).exclude(pk__in=asignadas).select_related(
        "estudiante", "convenio__empresa") if not u.es_admin else Solicitud.objects.none()
    return render(request, "tutor/solicitudes.html", {"asignadas": asignadas, "de_convenios": de_convenios})


@permisos.tutor
def tut_planes(request):
    planes = PlanPracticas.objects.filter(solicitud__in=solicitudes_de_tutor(request.user)).select_related(
        "solicitud__estudiante", "solicitud__convenio__empresa").order_by("-actualizado")
    return render(request, "tutor/planes.html", {"planes": planes})


@permisos.tutor
def tut_plan_revisar(request, pk):
    plan = get_object_or_404(PlanPracticas, pk=pk, solicitud__in=solicitudes_de_tutor(request.user))
    form = TextoForm(request.POST or None)
    if request.method == "POST":
        accion = request.POST.get("accion")
        texto = request.POST.get("texto", "").strip()
        if texto:
            ComentarioPlan.objects.create(plan=plan, autor=request.user, texto=texto)
        if accion in ("APROBADO", "RECHAZADO"):
            if accion == "RECHAZADO" and not texto:
                messages.error(request, "Escriba un comentario indicando el motivo del rechazo.")
                return redirect("tut_plan_revisar", pk)
            plan.estado = accion
            plan.save()
            notificar(plan.solicitud.estudiante, f"Plan de prácticas {plan.get_estado_display().lower()}",
                      f"Su plan de prácticas fue {plan.get_estado_display().lower()}. {texto}")
            messages.success(request, f"Plan {plan.get_estado_display().lower()}.")
        elif texto:
            notificar(plan.solicitud.estudiante, "Nuevo comentario en su plan", texto)
            messages.success(request, "Comentario agregado.")
        return redirect("tut_plan_revisar", pk)
    return render(request, "tutor/plan_revisar.html", {"plan": plan, "s": plan.solicitud, "form": form})


@permisos.tutor
def tut_informes(request):
    informes = InformeFinal.objects.filter(solicitud__in=solicitudes_de_tutor(request.user)).select_related(
        "solicitud__estudiante", "solicitud__convenio__empresa").order_by("-actualizado")
    return render(request, "tutor/informes.html", {"informes": informes})


@permisos.tutor
def tut_informe_revisar(request, pk):
    inf = get_object_or_404(InformeFinal, pk=pk, solicitud__in=solicitudes_de_tutor(request.user))
    form = TextoForm(request.POST or None)
    if request.method == "POST":
        accion = request.POST.get("accion")
        texto = request.POST.get("texto", "").strip()
        if accion in ("CORRECCION", "RECHAZADO") and not texto:
            messages.error(request, "Describa las correcciones u observaciones para el estudiante.")
            return redirect("tut_informe_revisar", pk)
        if texto:
            ObservacionInforme.objects.create(informe=inf, autor=request.user, texto=texto, version=inf.version)
        if accion in ("APROBADO", "RECHAZADO", "CORRECCION"):
            inf.estado = accion
            inf.save()
            notificar(inf.solicitud.estudiante, f"Informe final: {inf.get_estado_display()}",
                      f"Su informe final quedó en estado '{inf.get_estado_display()}'. {texto}")
            messages.success(request, f"Informe marcado como: {inf.get_estado_display()}.")
        return redirect("tut_informe_revisar", pk)
    return render(request, "tutor/informe_revisar.html", {"inf": inf, "s": inf.solicitud, "form": form})


@permisos.tutor
@require_POST
def tut_generar_aprobacion(request, solicitud_id):
    s = get_object_or_404(solicitudes_de_tutor(request.user), pk=solicitud_id)
    inf = getattr(s, "informe", None)
    if not inf or inf.estado != InformeFinal.Estado.APROBADO:
        messages.error(request, "El informe final debe estar aprobado.")
        return redirect("solicitud_detalle", s.pk)
    ev = getattr(s, "evaluacion", None)
    if not ev or not ev.archivo_firmado:
        messages.error(request, "Falta la evaluación del tutor empresarial (FPP08) firmada y cargada por el estudiante.")
        return redirect("solicitud_detalle", s.pk)
    cert, creado = Certificado.objects.get_or_create(
        tipo=Certificado.Tipo.APROBACION, solicitud=s,
        defaults={"estudiante": s.estudiante, "emitido_por": request.user},
    )
    if creado:
        notificar(s.estudiante, "Certificado de aprobación emitido",
                  f"Se emitió su certificado de aprobación de la práctica {s.numero_practica} ({cert.codigo}).")
        messages.success(request, "Certificado de aprobación generado.")
    return redirect("solicitud_detalle", s.pk)


# ===========================================================================
# DOCENTE-COORDINADOR
# ===========================================================================
@permisos.coordinador
def coo_empresas(request):
    return render(request, "coordinador/empresas.html", {
        "empresas": Empresa.objects.annotate(n=Count("convenios"))})


@permisos.coordinador
def coo_empresa_form(request, pk=None):
    inst = get_object_or_404(Empresa, pk=pk) if pk else None
    form = EmpresaForm(request.POST or None, instance=inst)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Empresa guardada.")
        return redirect("coo_empresas")
    return render(request, "form.html", {"form": form, "titulo": "Empresa / institución", "volver": "coo_empresas"})


@permisos.coordinador
def coo_empresa_eliminar(request, pk):
    e = get_object_or_404(Empresa, pk=pk)
    if request.method == "POST":
        if e.convenios.exists():
            messages.error(request, "No se puede eliminar: la empresa tiene convenios registrados.")
        else:
            e.delete()
            messages.success(request, "Empresa eliminada.")
        return redirect("coo_empresas")
    return render(request, "confirmar.html", {"objeto": e, "volver": "coo_empresas"})


@permisos.coordinador
def coo_convenios(request):
    qs = Convenio.objects.select_related("empresa").prefetch_related("carreras", "tutores")
    return render(request, "coordinador/convenios.html", {"convenios": qs})


@permisos.coordinador
def coo_convenio_form(request, pk=None):
    inst = get_object_or_404(Convenio, pk=pk) if pk else None
    form = ConvenioForm(request.POST or None, request.FILES or None, instance=inst)
    if request.method == "POST" and form.is_valid():
        c = form.save()
        te = getattr(form, "tutor_creado", None)
        if te:
            messages.success(request, f"Tutor empresarial {te.get_full_name()} registrado: ingresa con la cédula "
                                      f"{te.cedula} (contraseña inicial: la misma cédula).")
        messages.success(request, "Convenio guardado. Ahora puede asignarle docentes-tutores.")
        return redirect("coo_convenio_tutores", c.pk)
    return render(request, "coordinador/convenio_form.html", {"form": form})


@permisos.coordinador
def coo_convenio_eliminar(request, pk):
    c = get_object_or_404(Convenio, pk=pk)
    if request.method == "POST":
        if c.solicitudes.exists():
            messages.error(request, "No se puede eliminar: hay solicitudes asociadas. Desactívelo en su lugar.")
        else:
            c.delete()
            messages.success(request, "Convenio eliminado.")
        return redirect("coo_convenios")
    return render(request, "confirmar.html", {"objeto": c, "volver": "coo_convenios"})


@permisos.coordinador
def coo_convenio_tutores(request, pk):
    """Asignación de docentes-tutores a un convenio."""
    c = get_object_or_404(Convenio, pk=pk)
    tutores_carrera = Usuario.objects.filter(rol="TUTOR", carreras_tutoria__in=c.carreras.all()).distinct()
    form = TutoresForm(request.POST or None, initial={"tutores": c.tutores.all()})
    if tutores_carrera.exists():
        form.fields["tutores"].queryset = tutores_carrera
    if request.method == "POST" and form.is_valid():
        c.tutores.set(form.cleaned_data["tutores"])
        messages.success(request, "Docentes-tutores asignados al convenio.")
        return redirect("coo_convenios")
    return render(request, "coordinador/asignar_tutores.html", {
        "form": form, "titulo": f"Docentes-tutores del convenio {c.codigo}", "subtitulo": c.empresa.nombre,
        "ayuda": "Se listan los tutores asignados a las carreras del convenio." if tutores_carrera.exists() else
                 "Aún no hay tutores asignados a las carreras de este convenio; se muestran todos.",
    })


@permisos.coordinador
def coo_tutores_carrera(request):
    carreras = Carrera.objects.prefetch_related("tutores")
    return render(request, "coordinador/tutores_carrera.html", {"carreras": carreras})


@permisos.coordinador
def coo_carrera_tutores(request, pk):
    """Asignación de docentes-tutores por carrera."""
    c = get_object_or_404(Carrera, pk=pk)
    form = TutoresForm(request.POST or None, initial={"tutores": c.tutores.all()})
    if request.method == "POST" and form.is_valid():
        c.tutores.set(form.cleaned_data["tutores"])
        messages.success(request, f"Tutores de {c.nombre} actualizados.")
        return redirect("coo_tutores_carrera")
    return render(request, "coordinador/asignar_tutores.html", {
        "form": form, "titulo": f"Docentes-tutores de la carrera {c.nombre}",
    })


@permisos.coordinador
def coo_solicitudes(request):
    estado = request.GET.get("estado", "PENDIENTE")
    qs = Solicitud.objects.select_related("estudiante__carrera", "convenio__empresa", "tutor")
    if estado:
        qs = qs.filter(estado=estado)
    return render(request, "coordinador/solicitudes.html", {
        "solicitudes": qs, "estado": estado, "estados": Solicitud.Estado.choices,
    })


@permisos.coordinador
def coo_solicitud_revisar(request, pk):
    s = get_object_or_404(Solicitud, pk=pk)
    form = DecisionSolicitudForm(request.POST or None, solicitud=s)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        s.estado = d["accion"]
        s.observacion = d["observacion"]
        if d["accion"] == "APROBADO":
            s.tutor = d["tutor"]
            if not s.convenio.tutores.filter(pk=s.tutor.pk).exists():
                s.convenio.tutores.add(s.tutor)
        s.save()
        if s.estado == Solicitud.Estado.APROBADO and not hasattr(s, "carta"):
            # Se genera la solicitud de carta de aceptación para firma del Rector
            CartaAceptacion.objects.create(
                solicitud=s, numero=f"ISTAM-CA-{timezone.now():%Y}-{s.pk:04d}")
        notificar(s.estudiante, f"Solicitud de prácticas: {s.get_estado_display()}",
                  f"Su solicitud en {s.convenio.empresa} fue {s.get_estado_display().lower()}. {s.observacion}")
        if s.tutor and s.estado == "APROBADO":
            notificar(s.tutor, "Nuevo estudiante asignado",
                      f"Se le asignó como docente-tutor de {s.estudiante.get_full_name()}.")
        messages.success(request, f"Solicitud {s.get_estado_display().lower()}.")
        return redirect("coo_solicitudes")
    return render(request, "coordinador/solicitud_revisar.html", {"s": s, "form": form})


def _pendientes_culminacion():
    """Prácticas con certificado de aprobación del tutor y sin certificado de culminación."""
    return (Solicitud.objects.filter(certificados__tipo="APROBACION")
            .exclude(certificados__tipo="CULMINACION")
            .select_related("estudiante", "convenio__empresa", "informe").distinct())


@permisos.coordinador
def coo_culminacion(request):
    emitidos = Certificado.objects.filter(tipo="CULMINACION").select_related(
        "estudiante", "solicitud__convenio__empresa")[:50]
    return render(request, "coordinador/culminacion.html", {
        "pendientes": _pendientes_culminacion(), "emitidos": emitidos})


@permisos.coordinador
@require_POST
def coo_generar_culminacion(request, solicitud_id):
    s = get_object_or_404(Solicitud, pk=solicitud_id)
    if not s.certificados.filter(tipo="APROBACION").exists():
        messages.error(request, "Falta el certificado de aprobación del docente-tutor.")
    elif not (hasattr(s, "informe") and s.informe.certificado_empresa):
        messages.error(request, "El estudiante aún no carga el certificado emitido por la empresa.")
    else:
        try:
            cert = Certificado.objects.create(tipo="CULMINACION", solicitud=s, estudiante=s.estudiante,
                                              emitido_por=request.user)
            notificar(s.estudiante, "Certificado de culminación emitido",
                      f"Se emitió su certificado de culminación de la práctica {s.numero_practica} ({cert.codigo}).")
            messages.success(request, "Certificado de culminación generado.")
        except IntegrityError:
            messages.info(request, "Ya existe el certificado de culminación de esta práctica.")
    return redirect("coo_culminacion")


# ===========================================================================
# RECTOR
# ===========================================================================
@permisos.rector
def rec_cartas(request):
    cartas = CartaAceptacion.objects.select_related(
        "solicitud__estudiante", "solicitud__convenio__empresa").order_by("estado", "-creado")
    return render(request, "rector/cartas.html", {"cartas": cartas})


@permisos.rector
def rec_carta_pdf(request, pk):
    """Solicitud de carta de aceptación generada por el sistema (para imprimir y firmar)."""
    carta = get_object_or_404(CartaAceptacion, pk=pk)
    rector = request.user if request.user.rol == "RECTOR" else (
        Usuario.objects.filter(rol="RECTOR").first() or request.user)
    return pdf_respuesta(solicitud_carta_pdf(carta, rector), f"solicitud_carta_{carta.numero}.pdf")


@permisos.rector
def rec_carta_subir(request, pk):
    carta = get_object_or_404(CartaAceptacion, pk=pk)
    if carta.estado in ("ACEPTADA", "NO_ACEPTADA"):
        messages.error(request, "La empresa ya respondió esta solicitud.")
        return redirect("rec_cartas")
    form = ArchivoFirmadoForm(request.POST or None, request.FILES or None, instance=carta)
    if request.method == "POST" and form.is_valid():
        c = form.save(commit=False)
        if c.estado == CartaAceptacion.Estado.POR_FIRMAR:
            c.estado = CartaAceptacion.Estado.FIRMADA
        c.save()
        messages.success(request, "Solicitud firmada cargada. Ya puede enviarla al tutor empresarial.")
        return redirect("rec_cartas")
    return render(request, "form.html", {
        "form": form, "titulo": f"Cargar solicitud firmada {carta.numero}", "subtitulo": str(carta.solicitud),
        "volver": "rec_cartas", "multipart": True,
    })


@permisos.rector
@require_POST
def rec_carta_enviar(request, pk):
    """Envía por correo la solicitud firmada al tutor empresarial."""
    carta = get_object_or_404(CartaAceptacion, pk=pk)
    s = carta.solicitud
    conv = s.convenio
    te = conv.tutor_empresarial
    if not carta.archivo_firmado:
        messages.error(request, "Primero cargue la solicitud firmada.")
        return redirect("rec_cartas")
    if carta.estado in ("ACEPTADA", "NO_ACEPTADA"):
        messages.error(request, "La empresa ya respondió esta solicitud.")
        return redirect("rec_cartas")
    if not te or not te.email:
        messages.error(request, f"El convenio {conv.codigo} no tiene tutor empresarial con correo. "
                                "El coordinador debe asignarlo en el convenio.")
        return redirect("rec_cartas")
    enlace = request.build_absolute_uri(reverse("te_carta", args=[carta.pk]))
    correo = EmailMessage(
        subject=f"Solicitud de carta de aceptación de prácticas - {s.estudiante.get_full_name()}",
        body=(f"Estimado(a) {te.get_full_name()},\n\n"
              f"Adjunto remitimos la solicitud de carta de aceptación de prácticas preprofesionales del/la "
              f"estudiante {s.estudiante.get_full_name()}, de la carrera de {s.estudiante.carrera}, en el marco "
              f"del convenio {conv.codigo} con {conv.empresa}.\n\n"
              f"Para generar la carta de aceptación, ingrese al sistema con su cédula:\n{enlace}\n"
              f"(Si es su primer ingreso, la contraseña es su número de cédula.)\n\n"
              f"Atentamente,\n{settings.INSTITUCION_NOMBRE}"),
        from_email=settings.DEFAULT_FROM_EMAIL, to=[te.email],
        cc=[x for x in [conv.empresa.correo] if x],
    )
    carta.archivo_firmado.open("rb")
    correo.attach(f"solicitud_carta_{carta.numero}.pdf", carta.archivo_firmado.read(), "application/pdf")
    carta.archivo_firmado.close()
    try:
        correo.send()
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"No se pudo enviar el correo: {exc}")
        return redirect("rec_cartas")
    carta.estado = CartaAceptacion.Estado.ENVIADA
    carta.fecha_envio = timezone.now()
    carta.enviada_a = te.email
    carta.save()
    notificar(s.estudiante, "Solicitud de carta enviada a la empresa",
              f"El Rectorado envió la solicitud de carta de aceptación a {te.get_full_name()} ({conv.empresa}).")
    messages.success(request, f"Solicitud enviada al tutor empresarial {te.get_full_name()} ({te.email}).")
    return redirect("rec_cartas")


# ===========================================================================
# TUTOR EMPRESARIAL
# ===========================================================================
@permisos.tutor_emp
def te_solicitudes(request):
    cartas = cartas_de_tutor_emp(request.user).order_by("-fecha_envio")
    return render(request, "tutor_emp/solicitudes.html", {
        "pendientes": [c for c in cartas if c.estado == "ENVIADA"],
        "respondidas": [c for c in cartas if c.estado != "ENVIADA"],
    })


@permisos.tutor_emp
def te_carta(request, pk):
    """El tutor empresarial ve la solicitud y genera (o no) la carta de aceptación."""
    carta = get_object_or_404(cartas_de_tutor_emp(request.user), pk=pk)
    s = carta.solicitud
    form = RespuestaCartaForm(request.POST or None, request.FILES or None, instance=carta)
    if request.method == "POST":
        if carta.estado != CartaAceptacion.Estado.ENVIADA:
            messages.error(request, "Esta solicitud ya fue respondida.")
            return redirect("te_carta", pk)
        if form.is_valid():
            c = form.save(commit=False)
            c.estado = form.cleaned_data["decision"]
            c.respondida_por = request.user
            c.fecha_respuesta = timezone.now()
            c.save()
            if c.aceptada:
                _enviar_carta_aceptacion(c)
                messages.success(request, "Carta de aceptación generada y enviada al Rector y al estudiante.")
            else:
                s.estado = Solicitud.Estado.RECHAZADO
                s.observacion = f"La empresa no aceptó la práctica: {c.observacion_empresa}"
                s.save()
                for dest in [s.estudiante, *Usuario.objects.filter(rol="RECTOR", is_active=True)]:
                    notificar(dest, "La empresa no aceptó la práctica",
                              f"{s.convenio.empresa} no aceptó la práctica de {s.estudiante.get_full_name()}. "
                              f"Motivo: {c.observacion_empresa}")
                messages.info(request, "Se registró que no acepta al estudiante. Se notificó al Rector y al estudiante.")
            return redirect("te_carta", pk)
    return render(request, "tutor_emp/carta.html", {"carta": carta, "s": s, "form": form})


# ---------------------------- Evaluación FPP08 -----------------------------
def practicas_de_tutor_emp(user):
    qs = Solicitud.objects.filter(carta__estado=CartaAceptacion.Estado.ACEPTADA).select_related(
        "estudiante__carrera", "convenio__empresa", "tutor")
    return qs if user.es_admin else qs.filter(convenio__tutor_empresarial=user)


@permisos.tutor_emp
def te_evaluaciones(request):
    practicas = practicas_de_tutor_emp(request.user).order_by("-fecha_inicio")
    return render(request, "tutor_emp/evaluaciones.html", {"practicas": practicas})


@permisos.tutor_emp
def te_evaluacion(request, solicitud_id):
    s = get_object_or_404(practicas_de_tutor_emp(request.user), pk=solicitud_id)
    ev = getattr(s, "evaluacion", None)
    if ev and not ev.editable and request.method == "POST":
        messages.error(request, "El estudiante ya subió la evaluación firmada; no puede modificarse.")
        return redirect("te_evaluacion", s.pk)
    form = EvaluacionForm(request.POST or None, instance=ev)
    if request.method == "POST" and form.is_valid():
        ev = form.save(commit=False)
        ev.solicitud = s
        ev.evaluador = request.user
        ev.save()
        notificar(s.estudiante, "Evaluación del tutor empresarial registrada",
                  f"{request.user.get_full_name()} registró su evaluación (nota {ev.nota_final:.2f}/10). "
                  "Descárguela desde el sistema, imprímala, fírmela junto con su tutor empresarial y súbala.")
        messages.success(request, f"Evaluación guardada. Nota final: {ev.nota_final:.2f} / 10. "
                                  "Imprímala para firmarla junto con el estudiante.")
        return redirect("te_evaluacion", s.pk)
    filas = [(c, g, t, form[c]) for c, g, t in ASPECTOS_FPP08]
    return render(request, "tutor_emp/evaluacion.html", {
        "s": s, "ev": ev, "form": form, "filas": filas, "niveles": NIVELES_FPP08})


@login_required
def evaluacion_pdf(request, solicitud_id):
    s = get_object_or_404(Solicitud, pk=solicitud_id)
    ev = getattr(s, "evaluacion", None)
    if not ev or not puede_ver_solicitud(request.user, s):
        raise Http404
    return pdf_respuesta(evaluacion_fpp08_pdf(ev), f"FPP08_{s.estudiante.cedula}_practica{s.numero_practica}.pdf")


@login_required
def evaluacion_firmada_ver(request, solicitud_id):
    s = get_object_or_404(Solicitud, pk=solicitud_id)
    ev = getattr(s, "evaluacion", None)
    if not ev or not ev.archivo_firmado or not puede_ver_solicitud(request.user, s):
        raise Http404
    return FileResponse(ev.archivo_firmado.open("rb"), content_type="application/pdf")


@permisos.estudiante
def est_evaluacion_subir(request, solicitud_id):
    s = get_object_or_404(Solicitud, pk=solicitud_id, estudiante=request.user)
    ev = getattr(s, "evaluacion", None)
    if not ev:
        messages.error(request, "Su tutor empresarial aún no registra la evaluación.")
        return redirect("solicitud_detalle", s.pk)
    form = EvaluacionFirmadaForm(request.POST or None, request.FILES or None, instance=ev)
    if request.method == "POST" and form.is_valid():
        ev = form.save(commit=False)
        ev.fecha_subida = timezone.now()
        ev.save()
        notificar(s.tutor, "Evaluación FPP08 firmada cargada",
                  f"{request.user.get_full_name()} subió la evaluación firmada de su tutor empresarial.")
        messages.success(request, "Evaluación firmada cargada correctamente.")
        return redirect("solicitud_detalle", s.pk)
    return render(request, "form.html", {
        "form": form, "titulo": "Subir evaluación del tutor empresarial firmada (FPP08)",
        "subtitulo": f"{s} · Nota final: {ev.nota_final:.2f} / 10", "volver_url": s.pk, "multipart": True,
    })


def _enviar_carta_aceptacion(carta):
    """Envía la carta de aceptación al Rector y al estudiante."""
    s = carta.solicitud
    if carta.archivo_aceptacion:
        carta.archivo_aceptacion.open("rb")
        contenido = carta.archivo_aceptacion.read()
        carta.archivo_aceptacion.close()
    else:
        contenido = carta_aceptacion_empresa_pdf(carta)
    rectores = [r.email for r in Usuario.objects.filter(rol="RECTOR", is_active=True) if r.email]
    destinatarios = rectores + ([s.estudiante.email] if s.estudiante.email else [])
    if not destinatarios:
        return
    correo = EmailMessage(
        subject=f"Carta de aceptación de prácticas - {s.estudiante.get_full_name()} - {s.convenio.empresa}",
        body=(f"{s.convenio.empresa} ACEPTA al/la estudiante {s.estudiante.get_full_name()} para realizar su "
              f"práctica preprofesional N.º {s.numero_practica} en el área de {s.area}.\n"
              f"Horario: {carta.horario}\nTutor empresarial: {carta.respondida_por.get_full_name()}\n\n"
              "Se adjunta la carta de aceptación. El estudiante ya puede registrar su plan de prácticas "
              "en el sistema."),
        from_email=settings.DEFAULT_FROM_EMAIL, to=destinatarios,
        cc=[x for x in [s.tutor.email if s.tutor else ""] if x],
    )
    correo.attach(f"carta_aceptacion_{carta.numero}.pdf", contenido, "application/pdf")
    correo.send(fail_silently=True)


@login_required
def carta_aceptacion_descargar(request, pk):
    """Carta de aceptación de la empresa (la subida firmada o la generada por el sistema)."""
    carta = get_object_or_404(CartaAceptacion, pk=pk, estado=CartaAceptacion.Estado.ACEPTADA)
    if not puede_ver_solicitud(request.user, carta.solicitud):
        raise Http404
    if carta.archivo_aceptacion:
        return FileResponse(carta.archivo_aceptacion.open("rb"), content_type="application/pdf")
    return pdf_respuesta(carta_aceptacion_empresa_pdf(carta), f"carta_aceptacion_{carta.numero}.pdf")


@login_required
def carta_solicitud_ver(request, pk):
    """Solicitud firmada por el Rector (la ve el tutor empresarial y demás involucrados)."""
    carta = get_object_or_404(CartaAceptacion, pk=pk)
    if not carta.archivo_firmado or not puede_ver_solicitud(request.user, carta.solicitud):
        raise Http404
    return FileResponse(carta.archivo_firmado.open("rb"), content_type="application/pdf")


def _aptos_certificado_final():
    """Estudiantes con todas sus prácticas culminadas y sin certificado final."""
    aptos = []
    estudiantes = (Usuario.objects.filter(rol="ESTUDIANTE")
                   .annotate(culm=Count("certificados", filter=Q(certificados__tipo="CULMINACION")),
                             fin=Count("certificados", filter=Q(certificados__tipo="FINAL")))
                   .filter(culm__gt=0, fin=0).select_related("carrera"))
    for e in estudiantes:
        req = e.carrera.practicas_requeridas if e.carrera else 2
        if e.culm >= req:
            aptos.append(e)
    return aptos


@permisos.rector
def rec_finales(request):
    en_curso = (Usuario.objects.filter(rol="ESTUDIANTE")
                .annotate(culm=Count("certificados", filter=Q(certificados__tipo="CULMINACION")))
                .select_related("carrera"))
    emitidos = Certificado.objects.filter(tipo="FINAL").select_related("estudiante__carrera")
    return render(request, "rector/finales.html", {
        "aptos": _aptos_certificado_final(), "emitidos": emitidos, "en_curso": en_curso,
    })


@permisos.rector
@require_POST
def rec_generar_final(request, estudiante_id):
    est = get_object_or_404(Usuario, pk=estudiante_id, rol="ESTUDIANTE")
    if est not in _aptos_certificado_final():
        messages.error(request, "El estudiante no cumple las prácticas requeridas o ya tiene certificado final.")
        return redirect("rec_finales")
    cert = Certificado.objects.create(tipo="FINAL", estudiante=est, emitido_por=request.user)
    notificar(est, "Certificado final de prácticas emitido",
              f"El Rectorado emitió su certificado final de prácticas preprofesionales ({cert.codigo}). "
              "Este documento acredita su aptitud en este requisito para graduarse.")
    messages.success(request, f"Certificado final emitido para {est.get_full_name()}.")
    return redirect("rec_finales")


# ===========================================================================
# ADMINISTRADOR
# ===========================================================================
admin_requerido = permisos.rol_requerido()  # sin roles: solo el administrador


@admin_requerido
def adm_usuarios(request):
    rol = request.GET.get("rol", "")
    q = request.GET.get("q", "").strip()
    qs = Usuario.objects.select_related("carrera")
    if rol:
        qs = qs.filter(rol=rol)
    if q:
        qs = qs.filter(Q(cedula__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
                       | Q(email__icontains=q))
    return render(request, "admin_usuarios.html", {
        "usuarios": qs, "rol": rol, "q": q, "roles": Usuario.Rol.choices})


@admin_requerido
def adm_usuario_form(request, pk=None):
    inst = get_object_or_404(Usuario, pk=pk) if pk else None
    form = UsuarioForm(request.POST or None, instance=inst)
    if request.method == "POST" and form.is_valid():
        u = form.save()
        if not inst:
            messages.success(request, f"Usuario creado. Ingresa con la cédula {u.cedula} y la misma cédula como contraseña.")
        else:
            messages.success(request, "Usuario actualizado.")
        return redirect("adm_usuarios")
    return render(request, "form.html", {
        "form": form, "titulo": "Editar usuario" if inst else "Nuevo usuario", "volver": "adm_usuarios"})


@admin_requerido
def adm_carreras(request):
    carreras = Carrera.objects.annotate(
        n_estudiantes=Count("usuarios", filter=Q(usuarios__rol="ESTUDIANTE"), distinct=True),
        n_convenios=Count("convenios", distinct=True),
        n_tutores=Count("tutores", distinct=True),
    )
    return render(request, "admin_carreras.html", {"carreras": carreras})


@admin_requerido
def adm_carrera_form(request, pk=None):
    inst = get_object_or_404(Carrera, pk=pk) if pk else None
    form = CarreraForm(request.POST or None, instance=inst)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Carrera guardada.")
        return redirect("adm_carreras")
    return render(request, "form.html", {
        "form": form, "titulo": "Editar carrera" if inst else "Nueva carrera", "volver": "adm_carreras"})


@admin_requerido
def adm_carrera_eliminar(request, pk):
    c = get_object_or_404(Carrera, pk=pk)
    if request.method == "POST":
        if c.usuarios.exists() or c.convenios.exists():
            messages.error(request, "No se puede eliminar: la carrera tiene usuarios o convenios asociados.")
        else:
            c.delete()
            messages.success(request, "Carrera eliminada.")
        return redirect("adm_carreras")
    return render(request, "confirmar.html", {"objeto": c, "volver": "adm_carreras"})


@admin_requerido
def adm_carga_masiva(request):
    form = CargaMasivaForm(request.POST or None, request.FILES or None)
    resultado = None
    if request.method == "POST" and form.is_valid():
        try:
            resultado = procesar_archivo(form.cleaned_data["archivo"], form.cleaned_data["actualizar"])
        except ValueError as exc:
            messages.error(request, str(exc))
        except Exception:  # noqa: BLE001  archivo dañado o con otro formato
            messages.error(request, "No se pudo leer el archivo. Verifique que sea la plantilla en formato .xlsx o .csv.")
        else:
            messages.success(request, f"Carga terminada: {resultado['creados']} creados, "
                                      f"{resultado['actualizados']} actualizados, {resultado['omitidos']} omitidos, "
                                      f"{resultado['errores']} con errores.")
    return render(request, "admin_carga_masiva.html", {
        "form": form, "resultado": resultado, "carreras": Carrera.objects.all()})


@admin_requerido
def adm_plantilla(request):
    r = HttpResponse(generar_plantilla(),
                     content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r["Content-Disposition"] = 'attachment; filename="plantilla_usuarios_istam.xlsx"'
    return r


# ===========================================================================
# Cambio de contraseña (obligatorio en el primer ingreso)
# ===========================================================================
@login_required
def cambiar_clave(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    for campo in form.fields.values():
        campo.widget.attrs["class"] = "form-control"
    if request.method == "POST" and form.is_valid():
        u = form.save()
        u.debe_cambiar_clave = False
        u.save(update_fields=["debe_cambiar_clave"])
        update_session_auth_hash(request, u)
        messages.success(request, "Contraseña actualizada correctamente.")
        return redirect("inicio")
    return render(request, "cambiar_clave.html", {"form": form})
