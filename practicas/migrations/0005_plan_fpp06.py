# Plan de prácticas con el formato FPP06
import datetime

import django.core.validators
from django.db import migrations, models


def texto(nombre, largo, verbose, blank=False):
    return migrations.AddField(
        model_name="planpracticas", name=nombre,
        field=models.CharField(verbose_name=verbose, max_length=largo, default="", blank=blank),
        preserve_default=False,
    )


def correo(nombre, verbose, blank=True):
    return migrations.AddField(
        model_name="planpracticas", name=nombre,
        field=models.EmailField(verbose_name=verbose, max_length=254, default="", blank=blank),
        preserve_default=False,
    )


class Migration(migrations.Migration):
    dependencies = [("practicas", "0004_evaluacion_fpp08")]

    operations = [
        migrations.RemoveField(model_name="planpracticas", name="objetivo_general"),
        migrations.RemoveField(model_name="planpracticas", name="objetivos_especificos"),
        migrations.RemoveField(model_name="planpracticas", name="cronograma"),
        migrations.RemoveField(model_name="planpracticas", name="actividades"),
        texto("est_direccion", 200, "Dirección"),
        texto("est_telefono", 20, "Teléfono"),
        correo("est_email", "E-mail", blank=False),
        texto("emp_razon_social", 250, "Razón social"),
        texto("emp_direccion", 250, "Dirección"),
        texto("emp_ruc", 13, "RUC N.º", blank=True),
        texto("emp_telefono", 30, "Teléfono", blank=True),
        correo("emp_email", "E-mail"),
        texto("ger_nombre", 150, "Gerente / Representante"),
        texto("ger_telefono", 30, "Teléfono", blank=True),
        correo("ger_email", "E-mail"),
        texto("jefe_nombre", 150, "Jefe inmediato"),
        texto("jefe_cargo", 100, "Cargo", blank=True),
        correo("jefe_email", "E-mail"),
        texto("areas", 250, "Área(s) donde se realiza la práctica"),
        migrations.AddField(
            model_name="planpracticas", name="fecha_inicio",
            field=models.DateField(verbose_name="Fecha de inicio", default=datetime.date(2026, 1, 1)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="planpracticas", name="fecha_fin",
            field=models.DateField(verbose_name="Fecha de término", default=datetime.date(2026, 1, 1)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="planpracticas", name="resultados_aprendizaje",
            field=models.TextField(verbose_name="Resultados de aprendizaje", default="",
                                   help_text="Tomados del plan de prácticas del docente tutor."),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="planpracticas", name="actividades",
            field=models.JSONField(default=list, blank=True),
        ),
        migrations.AlterField(
            model_name="planpracticas", name="archivo",
            field=models.FileField(blank=True, upload_to="planes/", verbose_name="Plan firmado (PDF)",
                                   validators=[django.core.validators.FileExtensionValidator(["pdf"])]),
        ),
    ]
