from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Carrera, CartaAceptacion, Certificado, ComentarioPlan, Convenio, Empresa, EvaluacionEmpresarial,
    InformeFinal, ObservacionInforme, PlanPracticas, Solicitud, Usuario,
)

admin.site.site_header = "ISTAM - Administración de Prácticas Preprofesionales"
admin.site.site_title = "Prácticas ISTAM"


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("cedula", "get_full_name", "email", "rol", "carrera", "is_active")
    list_filter = ("rol", "carrera", "is_active")
    search_fields = ("username", "first_name", "last_name", "cedula", "email")
    fieldsets = UserAdmin.fieldsets + (
        ("Datos ISTAM", {"fields": ("rol", "cedula", "telefono", "carrera", "empresa", "cargo", "debe_cambiar_clave")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Datos ISTAM", {"fields": ("first_name", "last_name", "email", "rol", "cedula", "carrera")}),
    )


@admin.register(Carrera)
class CarreraAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "practicas_requeridas", "horas_por_practica")
    filter_horizontal = ("tutores",)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "ruc", "tipo", "correo")
    search_fields = ("nombre", "ruc")


@admin.register(Convenio)
class ConvenioAdmin(admin.ModelAdmin):
    list_display = ("codigo", "empresa", "tutor_empresarial", "fecha_inicio", "fecha_fin", "activo")
    list_filter = ("activo", "carreras")
    filter_horizontal = ("carreras", "tutores")


class ComentarioInline(admin.TabularInline):
    model = ComentarioPlan
    extra = 0


class ObservacionInline(admin.TabularInline):
    model = ObservacionInforme
    extra = 0


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = ("estudiante", "convenio", "numero_practica", "estado", "tutor", "creado")
    list_filter = ("estado", "numero_practica")


@admin.register(PlanPracticas)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("solicitud", "estado", "actualizado")
    inlines = [ComentarioInline]


@admin.register(InformeFinal)
class InformeAdmin(admin.ModelAdmin):
    list_display = ("solicitud", "estado", "version", "actualizado")
    inlines = [ObservacionInline]


@admin.register(CartaAceptacion)
class CartaAdmin(admin.ModelAdmin):
    list_display = ("numero", "solicitud", "estado", "fecha_envio")


@admin.register(Certificado)
class CertificadoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "tipo", "estudiante", "emitido_por", "fecha")
    list_filter = ("tipo",)


@admin.register(EvaluacionEmpresarial)
class EvaluacionAdmin(admin.ModelAdmin):
    list_display = ("solicitud", "evaluador", "nota_final", "fecha_subida")
