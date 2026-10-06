"""Control de acceso por rol. El Administrador puede acceder a todo."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def rol_requerido(*roles):
    def decorador(vista):
        @login_required
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if request.user.tiene_rol(*roles):
                return vista(request, *args, **kwargs)
            messages.error(request, "No tiene permiso para acceder a esa sección.")
            return redirect("inicio")
        return envoltura
    return decorador


estudiante = rol_requerido("ESTUDIANTE")
tutor = rol_requerido("TUTOR")
coordinador = rol_requerido("COORDINADOR")
rector = rol_requerido("RECTOR")
tutor_emp = rol_requerido("TUTOR_EMP")
