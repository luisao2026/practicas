from django import template
from django.utils.html import format_html

register = template.Library()

COLORES = {
    "PENDIENTE": "warning", "APROBADO": "success", "RECHAZADO": "danger", "DEVUELTO": "info",
    "CORRECCION": "info", "POR_FIRMAR": "warning", "FIRMADA": "primary", "ENVIADA": "info",
    "ACEPTADA": "success", "NO_ACEPTADA": "danger",
}


@register.simple_tag
def estado(obj):
    """Muestra el estado de un objeto como etiqueta de color."""
    color = COLORES.get(obj.estado, "secondary")
    texto = "text-dark" if color in ("warning", "info") else ""
    return format_html('<span class="badge bg-{} {}">{}</span>', color, texto, obj.get_estado_display())


@register.filter
def lineas(texto):
    return [l for l in (texto or "").splitlines() if l.strip()]
