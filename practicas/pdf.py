"""Generación de documentos PDF (carta de aceptación y los 3 certificados)."""
import os
from xml.sax.saxutils import escape
from io import BytesIO

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Colores institucionales (logotipo ISTAM)
AZUL = colors.HexColor("#006526")      # verde oscuro (nombre conservado por compatibilidad)
DORADO = colors.HexColor("#91b423")    # verde lima
VERDE_SUAVE = colors.HexColor("#eef6e4")

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_larga(fecha=None):
    fecha = fecha or timezone.localdate()
    if hasattr(fecha, "date") and callable(fecha.date):
        fecha = timezone.localtime(fecha).date()
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def _estilos():
    base = getSampleStyleSheet()
    return {
        "inst": ParagraphStyle("inst", parent=base["Title"], fontSize=15, textColor=AZUL, spaceAfter=2),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontSize=9, alignment=TA_CENTER, textColor=colors.grey),
        "titulo": ParagraphStyle("titulo", parent=base["Title"], fontSize=20, textColor=AZUL, spaceBefore=18, spaceAfter=14),
        "cuerpo": ParagraphStyle("cuerpo", parent=base["Normal"], fontSize=11.5, leading=18, alignment=TA_JUSTIFY),
        "centro": ParagraphStyle("centro", parent=base["Normal"], fontSize=11.5, leading=18, alignment=TA_CENTER),
        "nombre": ParagraphStyle("nombre", parent=base["Title"], fontSize=22, textColor=DORADO, spaceBefore=6, spaceAfter=6),
        "firma": ParagraphStyle("firma", parent=base["Normal"], fontSize=10, alignment=TA_CENTER, leading=13),
        "pie": ParagraphStyle("pie", parent=base["Normal"], fontSize=8, alignment=TA_CENTER, textColor=colors.grey),
    }


def _encabezado(e):
    logo = _logo(7, horizontal=True)
    if logo:
        logo.hAlign = "CENTER"
        cabecera = [logo, Spacer(1, 4)]
    else:
        cabecera = [Paragraph(settings.INSTITUCION_NOMBRE, e["inst"])]
    return [
        *cabecera,
        Paragraph("Unidad de Vinculación con la Sociedad y Prácticas Preprofesionales", e["sub"]),
        Spacer(1, 4),
        Table([[""]], colWidths=["100%"], style=[("LINEBELOW", (0, 0), (-1, -1), 2, DORADO)]),
    ]


def _firma(e, nombre, cargo, ancho):
    t = Table(
        [[Paragraph(f"______________________________<br/><b>{nombre}</b><br/>{cargo}", e["firma"])]],
        colWidths=[ancho],
    )
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    return t


def _marco(canvas, doc):
    canvas.saveState()
    w, h = doc.pagesize
    canvas.setStrokeColor(AZUL)
    canvas.setLineWidth(3)
    canvas.rect(1 * cm, 1 * cm, w - 2 * cm, h - 2 * cm)
    canvas.setStrokeColor(DORADO)
    canvas.setLineWidth(1)
    canvas.rect(1.25 * cm, 1.25 * cm, w - 2.5 * cm, h - 2.5 * cm)
    canvas.restoreState()


def _construir(historia, apaisado=False, marco=False):
    buffer = BytesIO()
    tam = landscape(A4) if apaisado else A4
    doc = SimpleDocTemplate(buffer, pagesize=tam, leftMargin=2.3 * cm, rightMargin=2.3 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    if marco:
        doc.build(historia, onFirstPage=_marco)
    else:
        doc.build(historia)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
def solicitud_carta_pdf(carta, rector):
    """Solicitud de carta de aceptación que firma el Rector y se envía al tutor empresarial."""
    s = carta.solicitud
    est, conv = s.estudiante, s.convenio
    te = conv.tutor_empresarial
    e = _estilos()
    h = _encabezado(e)
    destinatario = (f"<b>{te.get_full_name()}</b><br/>{te.cargo or 'Tutor Empresarial'}" if te
                    else f"<b>{conv.rep_legal_nombre}</b><br/>{conv.rep_legal_cargo or 'Representante Legal'}")
    h += [
        Spacer(1, 16),
        Paragraph(f"Oficio N.º {carta.numero}", e["cuerpo"]),
        Paragraph(f"{settings.INSTITUCION_CIUDAD}, {fecha_larga(carta.creado)}", e["cuerpo"]),
        Spacer(1, 14),
        Paragraph(f"Señor(a)<br/>{destinatario}<br/><b>{conv.empresa.nombre}</b><br/>Presente.-", e["cuerpo"]),
        Spacer(1, 14),
        Paragraph("<b>Asunto:</b> Solicitud de carta de aceptación para prácticas preprofesionales", e["cuerpo"]),
        Spacer(1, 10),
        Paragraph(
            "De mi consideración:<br/><br/>"
            f"En el marco del convenio interinstitucional <b>{conv.codigo}</b> suscrito entre {conv.empresa.nombre} "
            f"y el {settings.INSTITUCION_NOMBRE}, me permito solicitar de la manera más comedida se "
            f"acepte al/la estudiante <b>{est.get_full_name()}</b>, con cédula de identidad N.º {est.cedula or '—'}, "
            f"de la carrera de <b>{est.carrera or '—'}</b>, para realizar su <b>práctica preprofesional N.º "
            f"{s.numero_practica}</b> en el área de <b>{s.area}</b>, por un total de <b>{s.horas} horas</b>, "
            f"desde el {fecha_larga(s.fecha_inicio)} hasta el {fecha_larga(s.fecha_fin)}.", e["cuerpo"]),
        Spacer(1, 8),
        Paragraph(
            f"El seguimiento académico estará a cargo del docente-tutor <b>{s.tutor or '—'}</b>, en coordinación "
            f"con usted como tutor/a empresarial. Le solicitamos emitir la carta de aceptación a través del "
            f"sistema de prácticas preprofesionales del instituto.", e["cuerpo"]),
        Spacer(1, 8),
        Paragraph("Por la atención favorable que se digne dar a la presente, anticipo mis sinceros agradecimientos.",
                  e["cuerpo"]),
        Spacer(1, 8),
        Paragraph("Atentamente,", e["cuerpo"]),
        Spacer(1, 50),
        _firma(e, rector.get_full_name() or rector.username, "RECTOR", 9 * cm),
    ]
    return _construir(h)


def carta_aceptacion_empresa_pdf(carta):
    """Carta de aceptación que emite la empresa (tutor empresarial) a través del sistema."""
    s = carta.solicitud
    est, conv = s.estudiante, s.convenio
    te = carta.respondida_por or conv.tutor_empresarial
    empresa = conv.empresa
    e = _estilos()
    rector = type(est).objects.filter(rol="RECTOR").first()
    h = [
        Paragraph(empresa.nombre.upper(), e["inst"]),
        Paragraph(" · ".join(x for x in [f"RUC {empresa.ruc}", empresa.direccion, empresa.telefono] if x), e["sub"]),
        Spacer(1, 4),
        Table([[""]], colWidths=["100%"], style=[("LINEBELOW", (0, 0), (-1, -1), 2, AZUL)]),
        Spacer(1, 16),
        Paragraph(f"Ref.: {carta.numero}", e["cuerpo"]),
        Paragraph(f"{settings.INSTITUCION_CIUDAD}, {fecha_larga(carta.fecha_respuesta or timezone.now())}",
                  e["cuerpo"]),
        Spacer(1, 14),
        Paragraph(f"Señor(a)<br/><b>{rector.get_full_name() if rector else 'Rector(a)'}</b><br/>RECTOR(A)<br/>"
                  f"<b>{settings.INSTITUCION_NOMBRE}</b><br/>Presente.-", e["cuerpo"]),
        Spacer(1, 14),
        Paragraph("<b>Asunto:</b> Carta de aceptación de prácticas preprofesionales", e["cuerpo"]),
        Spacer(1, 10),
        Paragraph(
            "De mi consideración:<br/><br/>"
            f"En atención al oficio N.º {carta.numero} y en el marco del convenio <b>{conv.codigo}</b>, "
            f"me permito comunicar que <b>{empresa.nombre}</b> <b>ACEPTA</b> al/la estudiante "
            f"<b>{est.get_full_name()}</b>, con cédula de identidad N.º {est.cedula or '—'}, de la carrera de "
            f"<b>{est.carrera or '—'}</b>, para que realice su <b>práctica preprofesional N.º {s.numero_practica}</b> "
            f"en nuestra institución, bajo las siguientes condiciones:", e["cuerpo"]),
        Spacer(1, 8),
    ]
    filas = [
        ["Área / departamento", s.area],
        ["Período", f"Del {fecha_larga(s.fecha_inicio)} al {fecha_larga(s.fecha_fin)}"],
        ["Total de horas", f"{s.horas} horas"],
        ["Horario", carta.horario or "—"],
        ["Tutor empresarial", f"{te.get_full_name()}{' – ' + te.cargo if te and te.cargo else ''}" if te else "—"],
        ["Docente-tutor ISTAM", str(s.tutor or "—")],
    ]
    t = Table(filas, colWidths=[5 * cm, 11.4 * cm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef1f6")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    h += [t, Spacer(1, 10)]
    if carta.observacion_empresa:
        h += [Paragraph(f"<b>Observaciones:</b> {carta.observacion_empresa}", e["cuerpo"]), Spacer(1, 8)]
    h += [
        Paragraph("Quien suscribe actuará como tutor/a empresarial, supervisando las actividades del estudiante "
                  "durante el período de prácticas.", e["cuerpo"]),
        Spacer(1, 8),
        Paragraph("Atentamente,", e["cuerpo"]),
        Spacer(1, 45),
        _firma(e, te.get_full_name() if te else "", f"{te.cargo or 'Tutor Empresarial'}<br/>{empresa.nombre}"
               if te else empresa.nombre, 10 * cm),
        Spacer(1, 12),
        Paragraph(f"Carta generada en el sistema de prácticas del {settings.INSTITUCION_NOMBRE} · Ref. {carta.numero}",
                  e["pie"]),
    ]
    return _construir(h)


# ---------------------------------------------------------------------------
TEXTOS = {
    "APROBACION": (
        "CERTIFICADO DE APROBACIÓN DE PRÁCTICAS PREPROFESIONALES",
        "Docente-tutor",
    ),
    "CULMINACION": (
        "CERTIFICADO DE CULMINACIÓN DE PRÁCTICAS PREPROFESIONALES",
        "Docente-coordinador de prácticas",
    ),
    "FINAL": (
        "CERTIFICADO FINAL DE PRÁCTICAS PREPROFESIONALES",
        "RECTOR",
    ),
}


def certificado_pdf(cert):
    e = _estilos()
    titulo, cargo = TEXTOS[cert.tipo]
    est = cert.estudiante
    h = _encabezado(e)
    h += [Paragraph(titulo, e["titulo"]), Paragraph("Se certifica que el/la estudiante:", e["centro"]),
          Paragraph(est.get_full_name().upper() or est.username, e["nombre"]),
          Paragraph(f"C.I. {est.cedula or '—'} &nbsp;·&nbsp; Carrera: <b>{est.carrera or '—'}</b>", e["centro"]),
          Spacer(1, 10)]

    if cert.tipo in ("APROBACION", "CULMINACION"):
        s = cert.solicitud
        horas = s.informe.horas_cumplidas if hasattr(s, "informe") else s.horas
        if cert.tipo == "APROBACION":
            texto = (f"ha <b>APROBADO</b> la práctica preprofesional N.º {s.numero_practica}, realizada en "
                     f"<b>{s.convenio.empresa.nombre}</b>, área de {s.area}, cumpliendo <b>{horas} horas</b> "
                     f"entre el {fecha_larga(s.fecha_inicio)} y el {fecha_larga(s.fecha_fin)}, habiendo sido "
                     "aprobados su plan de prácticas y su informe final.")
        else:
            texto = (f"ha <b>CULMINADO</b> satisfactoriamente la práctica preprofesional N.º {s.numero_practica} "
                     f"en <b>{s.convenio.empresa.nombre}</b> (convenio {s.convenio.codigo}), con un total de "
                     f"<b>{horas} horas</b>, según consta en el certificado de la entidad receptora y en el "
                     "certificado de aprobación del docente-tutor.")
        h.append(Paragraph(texto, e["centro"]))
    else:
        culminadas = (est.certificados.filter(tipo="CULMINACION")
                      .select_related("solicitud__convenio__empresa").order_by("solicitud__numero_practica"))
        h.append(Paragraph(
            "ha cumplido con la totalidad de las prácticas preprofesionales exigidas por su malla curricular, "
            "encontrándose <b>APTO/A</b> en este requisito para el proceso de titulación:", e["centro"]))
        h.append(Spacer(1, 8))
        filas = [["Práctica", "Entidad receptora", "Horas", "Cert. culminación"]]
        total = 0
        for c in culminadas:
            s = c.solicitud
            horas = s.informe.horas_cumplidas if hasattr(s, "informe") else s.horas
            total += horas
            filas.append([str(s.numero_practica), s.convenio.empresa.nombre, str(horas), c.codigo])
        filas.append(["", "TOTAL", str(total), ""])
        t = Table(filas, colWidths=[2.5 * cm, 9 * cm, 2.5 * cm, 6.5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), AZUL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]))
        h.append(t)

    h += [
        Spacer(1, 10),
        Paragraph(f"Dado en {settings.INSTITUCION_CIUDAD}, el {fecha_larga(cert.fecha)}.", e["centro"]),
        Spacer(1, 34),
        _firma(e, cert.emitido_por.get_full_name() or cert.emitido_por.username, cargo, 10 * cm),
        Spacer(1, 10),
        Paragraph(f"Código de verificación: <b>{cert.codigo}</b>", e["pie"]),
    ]
    return _construir(h, apaisado=True, marco=True)


# ---------------------------------------------------------------------------
# FORMATO FPP08 - Evaluación del desempeño por el tutor empresarial
# ---------------------------------------------------------------------------
def _logo(ancho_cm=2.6, horizontal=False):
    """Logo del instituto: el ícono (hoja) para los formatos FPP, el horizontal para cartas y certificados."""
    ruta = getattr(settings, "INSTITUCION_LOGO" if horizontal else "INSTITUCION_LOGO_ICONO", None)
    if ruta and os.path.exists(ruta):
        img = ImageReader(str(ruta))
        w, h = img.getSize()
        return Image(str(ruta), width=ancho_cm * cm, height=ancho_cm * cm * h / w)
    return ""


def evaluacion_fpp08_pdf(ev):
    from .models import ASPECTOS_FPP08, NIVELES_FPP08, nivel_fpp08

    s = ev.solicitud
    est, conv = s.estudiante, s.convenio
    te = ev.evaluador
    base = getSampleStyleSheet()
    chico = ParagraphStyle("chico", parent=base["Normal"], fontSize=8.5, leading=10.5)
    chico_b = ParagraphStyle("chico_b", parent=chico, fontName="Helvetica-Bold")
    centro_b = ParagraphStyle("centro_b", parent=chico_b, alignment=TA_CENTER)
    NEGRO = colors.black

    # Encabezado igual al formato: logo | institución | versión
    enc = Table([[
        _logo(),
        [Paragraph(f"<b>{settings.INSTITUCION_NOMBRE}</b>",
                   ParagraphStyle("t", parent=base["Normal"], fontSize=11, alignment=TA_CENTER, leading=14)),
         Paragraph(settings.INSTITUCION_UBICACION,
                   ParagraphStyle("u", parent=base["Normal"], fontSize=7, alignment=TA_CENTER))],
        [Paragraph("<b>Versión N°:</b> 3.0", chico), Spacer(1, 6), Paragraph("<b>Fecha:</b> 01/12/2022", chico)],
    ]], colWidths=[3.2 * cm, 10.3 * cm, 3.5 * cm])
    enc.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    h = [
        enc,
        Spacer(1, 4),
        Paragraph("<b>FORMATO FPP08</b>", ParagraphStyle("f", parent=base["Normal"], fontSize=11, alignment=TA_CENTER)),
        Spacer(1, 8),
        Paragraph("<u><b>EVALUACIÓN DEL DESEMPEÑO POR EL TUTOR EMPRESARIAL</b></u>",
                  ParagraphStyle("tt", parent=base["Normal"], fontSize=11, alignment=TA_CENTER)),
        Spacer(1, 10),
    ]

    # Datos informativos
    datos = [
        ("NOMBRE DEL ESTUDIANTE:", est.get_full_name().upper()),
        ("NOMBRE DE LA EMPRESA:", conv.empresa.nombre),
        ("ÁREA DONDE REALIZÓ LAS PRÁCTICAS:", s.area),
        ("NOMBRE DEL TUTOR EMPRESARIAL:", te.get_full_name()),
        ("CARGO:", te.cargo or ""),
        ("FECHA DE INICIO DE LAS PRÁCTICAS:", s.fecha_inicio.strftime("%d/%m/%Y")),
        ("FECHA DE TERMINACIÓN DE LAS PRÁCTICAS:", s.fecha_fin.strftime("%d/%m/%Y")),
    ]
    filas = [[Paragraph("DATOS INFORMATIVOS", centro_b), ""]]
    filas += [[Paragraph(e, chico_b), Paragraph(escape(v or ""), chico)] for e, v in datos]
    t = Table(filas, colWidths=[6.6 * cm, 10.4 * cm])
    t.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)), ("BOX", (0, 0), (-1, -1), 0.8, NEGRO), ("LINEBELOW", (0, 0), (-1, 0), 0.8, NEGRO),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ]))
    h.append(t)

    # Aspectos y niveles
    ancho_asp, ancho_niv = 7.4 * cm, 2.4 * cm
    cab1 = [Paragraph("ASPECTOS", centro_b), Paragraph("NIVEL DE DESEMPEÑO", centro_b), "", "", ""]
    cab2 = [""] + [Paragraph(f"{etq}<br/>({mn} – {mx})", centro_b) for _, etq, mn, mx in NIVELES_FPP08]
    filas = [cab1, cab2]
    estilos = [
        ("GRID", (0, 0), (-1, -1), 0.6, NEGRO), ("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (4, 0)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    claves = [n[0] for n in NIVELES_FPP08]
    grupo_actual = None
    for campo, grupo, texto in ASPECTOS_FPP08:
        if grupo != grupo_actual:
            filas.append([Paragraph(grupo, chico_b), "", "", "", ""])
            estilos.append(("SPAN", (0, len(filas) - 1), (-1, len(filas) - 1)))
            grupo_actual = grupo
        valor = getattr(ev, campo)
        fila = [Paragraph(texto, chico), "", "", "", ""]
        if valor is not None:
            fila[1 + claves.index(nivel_fpp08(valor))] = f"{valor:.3f}"
        filas.append(fila)
    sub = ev.subtotales
    filas.append([Paragraph("SUBTOTAL POR NIVEL:", ParagraphStyle("r", parent=chico_b, alignment=2))]
                 + [f"{sub[k]:.3f}" if sub[k] else "" for k in claves])
    filas.append([Paragraph("NOTA FINAL:", ParagraphStyle("r2", parent=chico_b, alignment=2)),
                  Paragraph(f"<b>{ev.nota_final:.2f} / 10</b>", centro_b), "", "", ""])
    estilos += [("SPAN", (1, len(filas) - 1), (4, len(filas) - 1)),
                ("FONTNAME", (1, len(filas) - 2), (-1, len(filas) - 2), "Helvetica-Bold")]
    t = Table(filas, colWidths=[ancho_asp] + [ancho_niv] * 4)
    t.setStyle(TableStyle(estilos))
    h.append(t)

    # Firmas (en blanco para firmar a mano)
    firmas = Table([
        [Paragraph("<b>TUTOR EMPRESARIAL:</b><br/><br/><br/>Firma:<br/><br/><br/>", chico),
         Paragraph("<b>ESTUDIANTE:</b><br/><br/><br/>Firma:<br/><br/><br/>", chico)],
        [Paragraph(f"Nombre: {te.get_full_name()}", chico), Paragraph("Fecha:", chico)],
    ], colWidths=[8.5 * cm, 8.5 * cm])
    firmas.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.6, NEGRO), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    h += [firmas, Spacer(1, 8),
          Paragraph(f"Registrado en el sistema el {timezone.localtime(ev.actualizado):%d/%m/%Y %H:%M} · "
                    f"Práctica N.º {s.numero_practica} · C.I. estudiante {est.cedula}", _estilos()["pie"])]

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.3 * cm, bottomMargin=1.3 * cm)
    doc.build(h)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# FORMATO FPP06 - Plan de prácticas del estudiante
# ---------------------------------------------------------------------------
def _encabezado_formato(codigo, base, chico):
    enc = Table([[
        _logo(),
        [Paragraph(f"<b>{settings.INSTITUCION_NOMBRE}</b>",
                   ParagraphStyle("t", parent=base["Normal"], fontSize=11, alignment=TA_CENTER, leading=14)),
         Paragraph(settings.INSTITUCION_UBICACION,
                   ParagraphStyle("u", parent=base["Normal"], fontSize=7, alignment=TA_CENTER))],
        [Paragraph("<b>Versión N°:</b> 3.0", chico), Spacer(1, 6), Paragraph("<b>Fecha:</b> 01/12/2022", chico)],
    ]], colWidths=[3.2 * cm, 10.3 * cm, 3.5 * cm])
    enc.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return [enc, Spacer(1, 4),
            Paragraph(f"<b>FORMATO {codigo}</b>",
                      ParagraphStyle("f", parent=base["Normal"], fontSize=11, alignment=TA_CENTER)),
            Spacer(1, 8)]


def plan_fpp06_pdf(plan):
    s = plan.solicitud
    est = s.estudiante
    base = getSampleStyleSheet()
    chico = ParagraphStyle("p6", parent=base["Normal"], fontSize=9, leading=11.5)
    seccion = ParagraphStyle("sec", parent=base["Normal"], fontSize=9.5, fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=3)
    mini = ParagraphStyle("mini", parent=base["Normal"], fontSize=6.5, leading=7.5, alignment=TA_CENTER)
    mini_b = ParagraphStyle("mini_b", parent=mini, fontName="Helvetica-Bold")
    nota = ParagraphStyle("nota", parent=base["Normal"], fontSize=6.5, leading=8)
    NEGRO = colors.black
    ANCHO = 17 * cm

    def P(etq, valor, salto=False):
        return Paragraph(f"{etq}{'<br/>' if salto else ' '}{escape(str(valor or ''))}", chico)

    def f(d):
        return d.strftime("%d/%m/%Y") if d else ""

    rejilla = [("GRID", (0, 0), (-1, -1), 0.6, NEGRO), ("VALIGN", (0, 0), (-1, -1), "TOP"),
               ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]

    h = _encabezado_formato("FPP06", base, chico)
    h.append(Paragraph("<u><b>PLAN DE PRÁCTICAS DEL ESTUDIANTE</b></u><super>1</super>",
                       ParagraphStyle("tt", parent=base["Normal"], fontSize=11, alignment=TA_CENTER)))
    h.append(Spacer(1, 8))

    # I. Datos del estudiante
    h.append(Paragraph("I.- DATOS DEL ESTUDIANTE:", seccion))
    t = Table([
        [P("Apellidos y Nombres:", f"{est.last_name} {est.first_name}".strip().upper()), ""],
        [P("Dirección:", plan.est_direccion), ""],
        [P("Teléfono:", plan.est_telefono), P("E-mail:", plan.est_email)],
    ], colWidths=[7.5 * cm, 9.5 * cm])
    t.setStyle(TableStyle(rejilla + [("SPAN", (0, 0), (1, 0)), ("SPAN", (0, 1), (1, 1))]))
    h.append(t)

    # II. Datos de la empresa
    h.append(Paragraph("II.- DATOS DE LA EMPRESA:", seccion))
    c = [7.4 * cm, 2.9 * cm, 3.2 * cm, 3.5 * cm]
    t = Table([
        [P("Razón Social:", plan.emp_razon_social), "", "", ""],
        [P("Dirección:", plan.emp_direccion), "", P("RUC Nº.", plan.emp_ruc), ""],
        [P("Teléfono:", plan.emp_telefono), P("E-mail:", plan.emp_email), "", ""],
        [P("Gerente / Representante:", plan.ger_nombre, True), P("Teléfono:", plan.ger_telefono, True),
         P("E-mail:", plan.ger_email, True), ""],
        [P("Jefe Inmediato:", plan.jefe_nombre), P("Cargo:", plan.jefe_cargo), P("E-mail:", plan.jefe_email), ""],
        [P("Área(s) donde se realiza la práctica:", plan.areas), "",
         P("Fecha de Inicio:", f(plan.fecha_inicio), True), P("Fecha de Término:", f(plan.fecha_fin), True)],
        [Paragraph("Resultados de aprendizaje<super>2</super>: "
                   + escape(plan.resultados_aprendizaje or "").replace("\n", "<br/>"),
                   chico), "", "", ""],
    ], colWidths=c)
    t.setStyle(TableStyle(rejilla + [
        ("SPAN", (0, 0), (3, 0)), ("SPAN", (0, 1), (1, 1)), ("SPAN", (2, 1), (3, 1)), ("SPAN", (1, 2), (3, 2)),
        ("SPAN", (2, 3), (3, 3)), ("SPAN", (2, 4), (3, 4)), ("SPAN", (0, 5), (1, 5)), ("SPAN", (0, 6), (3, 6)),
    ]))
    h.append(t)

    # III. Actividades y cronograma
    h.append(Paragraph("III.- ACTIVIDADES PRINCIPALES A REALIZARSE EN LA EMPRESA.<super>3</super>", seccion))
    n_sem = plan.semanas
    por_dia = n_sem <= 7          # hasta 7 semanas: una columna por día, como el formato; si no, por semana
    cols_sem = 5 if por_dia else 1
    n_cols = n_sem * cols_sem
    ancho_item = 1.0 * cm
    ancho_col = min((0.42 if por_dia else 0.85) * cm, (ANCHO - ancho_item - 5.2 * cm) / n_cols)
    ancho_act = ANCHO - ancho_item - ancho_col * n_cols

    fila_mes = [Paragraph("ITEM", mini_b), Paragraph("ACTIVIDADES", mini_b)] + [""] * n_cols
    fila_sem = ["", ""] + [""] * n_cols
    fila_dia = ["", ""] + [""] * n_cols
    estilo = [("GRID", (0, 0), (-1, -1), 0.5, NEGRO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTSIZE", (0, 0), (-1, -1), 6.5),
              ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
              ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 1),
              ("SPAN", (0, 0), (0, 2)), ("SPAN", (1, 0), (1, 2)),
              ("BACKGROUND", (0, 0), (-1, 2), VERDE_SUAVE)]
    for m in range(0, n_sem, 4):
        c0 = 2 + m * cols_sem
        c1 = 2 + min(n_sem, m + 4) * cols_sem - 1
        fila_mes[c0] = Paragraph(f"MES {m // 4 + 1}", mini_b)
        estilo.append(("SPAN", (c0, 0), (c1, 0)))
    for w in range(n_sem):
        c0 = 2 + w * cols_sem
        fila_sem[c0] = Paragraph(f"SEMANA {w + 1}" if por_dia else f"SEM<br/>{w + 1}", mini)
        if por_dia:
            estilo.append(("SPAN", (c0, 1), (c0 + 4, 1)))
            for d in range(5):
                fila_dia[c0 + d] = str(d + 1)
    if not por_dia:
        for w in range(n_sem):
            estilo.append(("SPAN", (2 + w, 1), (2 + w, 2)))

    filas = [fila_mes, fila_sem, fila_dia]
    texto_act = ParagraphStyle("act", parent=base["Normal"], fontSize=7.5, leading=9)
    actividades = plan.actividades or []
    for i, a in enumerate(actividades):
        fila = [str(i + 1), Paragraph(escape(a.get("actividad", "")), texto_act)] + [""] * n_cols
        r = len(filas)
        marcadas = set()
        for codigo in a.get("dias", []):
            sem, dia = (int(x) for x in codigo.split("-"))
            if sem <= n_sem:
                marcadas.add(2 + (sem - 1) * cols_sem + ((dia - 1) if por_dia else 0))
        for col in marcadas:
            estilo.append(("BACKGROUND", (col, r), (col, r), DORADO))
        filas.append(fila)
    for _ in range(max(0, 5 - len(actividades))):  # filas vacías como en el formato
        filas.append([""] * (2 + n_cols))
    estilo.append(("ALIGN", (1, 3), (1, -1), "LEFT"))
    t = Table(filas, colWidths=[ancho_item, ancho_act] + [ancho_col] * n_cols, repeatRows=3)
    t.setStyle(TableStyle(estilo))
    h.append(t)
    if not por_dia:
        h.append(Paragraph("Cronograma resumido por semanas (período mayor a 7 semanas).", nota))

    # Firmas
    h.append(Spacer(1, 16))
    te = s.convenio.tutor_empresarial
    nombre_te = te.get_full_name() if te else plan.jefe_nombre
    firmas = Table([
        [Paragraph("<b>TUTOR EMPRESARIAL:</b><br/><br/><font size=7>Firma:</font><br/><br/><br/>", chico),
         Paragraph("<b>TUTOR ACADÉMICO:</b><br/><br/><font size=7>Firma:</font><br/><br/><br/>", chico),
         Paragraph("<b>ESTUDIANTE:</b><br/><br/><font size=7>Firma:</font><br/><br/><br/>", chico)],
        [Paragraph(nombre_te or "", chico), Paragraph(str(s.tutor or ""), chico),
         Paragraph(f"{est.get_full_name()}<br/>Fecha:", chico)],
    ], colWidths=[ANCHO / 3] * 3)
    firmas.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.6, NEGRO), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    h.append(firmas)

    # Notas al pie del formato
    h += [Spacer(1, 14),
          Table([[""]], colWidths=[6 * cm], style=[("LINEABOVE", (0, 0), (-1, -1), 0.5, NEGRO)], hAlign="LEFT"),
          Paragraph("<super>1</super> Tomadas del plan de prácticas del docente tutor.", nota),
          Paragraph("<super>2</super> Tomado del plan de prácticas del docente; se puede adicionar actividades según el "
                    "requerimiento de la empresa. Comunicar al tutor académico.", nota),
          Paragraph("<super>3</super> Solicitar al tutor académico las actividades a desarrollar en la empresa.", nota)]

    def marca_agua(canvas, doc):
        if plan.estado != "APROBADO":
            canvas.saveState()
            canvas.setFont("Helvetica-Bold", 42)
            canvas.setFillColor(colors.Color(0.6, 0.6, 0.6, alpha=0.18))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(40)
            canvas.drawCentredString(0, 0, "BORRADOR - PENDIENTE DE APROBACIÓN")
            canvas.restoreState()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.3 * cm, bottomMargin=1.3 * cm)
    doc.build(h, onFirstPage=marca_agua, onLaterPages=marca_agua)
    return buffer.getvalue()
