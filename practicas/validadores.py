"""Validaciones propias de Ecuador."""
from django.core.exceptions import ValidationError


def cedula_valida(cedula: str) -> bool:
    """Verifica una cédula ecuatoriana (10 dígitos, provincia y dígito verificador módulo 10)."""
    if not cedula or len(cedula) != 10 or not cedula.isdigit():
        return False
    provincia = int(cedula[:2])
    if not (1 <= provincia <= 24 or provincia == 30):  # 30 = ecuatorianos registrados en el exterior
        return False
    if int(cedula[2]) >= 6:  # personas naturales
        return False
    suma = 0
    for i, d in enumerate(cedula[:9]):
        n = int(d) * (2 if i % 2 == 0 else 1)
        suma += n - 9 if n > 9 else n
    verificador = (10 - suma % 10) % 10
    return verificador == int(cedula[9])


def validar_cedula(valor):
    if not cedula_valida(str(valor)):
        raise ValidationError("La cédula %(valor)s no es válida.", params={"valor": valor})
