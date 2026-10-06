from django.shortcuts import redirect
from django.urls import reverse


class CambioClaveObligatorioMiddleware:
    """Si el usuario tiene la contraseña inicial (su cédula), lo lleva a cambiarla."""

    PERMITIDAS = ("cambiar_clave", "logout")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = getattr(request, "user", None)
        if u and u.is_authenticated and getattr(u, "debe_cambiar_clave", False):
            rutas = [reverse(n) for n in self.PERMITIDAS]
            if request.path not in rutas and not request.path.startswith(("/static/", "/media/")):
                return redirect("cambiar_clave")
        return self.get_response(request)
