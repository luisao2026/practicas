from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path

from practicas.views import media_protegida

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Archivos subidos: solo usuarios con permiso (ver practicas/views.py → media_protegida)
    re_path(r"^media/(?P<ruta>.+)$", media_protegida, name="media_protegida"),
    path("", include("practicas.urls")),
]
