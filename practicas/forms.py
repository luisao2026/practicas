from django import forms
from django.core.validators import FileExtensionValidator
from django.db.models import Q

from .validadores import cedula_valida
from .models import (
    ASPECTOS_FPP08, EvaluacionEmpresarial,
    Carrera, CartaAceptacion, Convenio, Empresa, InformeFinal, PlanPracticas,
    Solicitud, Usuario,
)


class BootstrapMixin:
    """Aplica clases de Bootstrap a todos los campos."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            w = campo.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", "form-select")
            else:
                w.attrs.setdefault("class", "form-control")


class FechaInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


def area(rows=3):
    return forms.Textarea(attrs={"rows": rows})


# ----------------------------- Estudiante ---------------------------------
class SolicitudForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Solicitud
        fields = ["convenio", "numero_practica", "area", "fecha_inicio", "fecha_fin", "horas", "motivo"]
        widgets = {"fecha_inicio": FechaInput(), "fecha_fin": FechaInput(), "motivo": area()}

    def __init__(self, *args, estudiante=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Convenio.objects.filter(activo=True)
        if estudiante and estudiante.carrera_id:
            qs = qs.filter(carreras=estudiante.carrera)
        self.fields["convenio"].queryset = qs.select_related("empresa")
        maximo = estudiante.carrera.practicas_requeridas if estudiante and estudiante.carrera else 2
        self.fields["numero_practica"].widget = forms.Select(
            choices=[(i, f"Práctica {i}") for i in range(1, maximo + 1)], attrs={"class": "form-select"}
        )
        self.estudiante = estudiante

    def clean(self):
        datos = super().clean()
        ini, fin = datos.get("fecha_inicio"), datos.get("fecha_fin")
        if ini and fin and fin <= ini:
            self.add_error("fecha_fin", "La fecha de fin debe ser posterior a la de inicio.")
        num = datos.get("numero_practica")
        if self.estudiante and num:
            repetida = Solicitud.objects.filter(
                estudiante=self.estudiante, numero_practica=num,
            ).exclude(estado=Solicitud.Estado.RECHAZADO).exclude(pk=self.instance.pk)
            if repetida.exists():
                self.add_error("numero_practica", f"Ya tiene una solicitud activa para la práctica {num}.")
        return datos


class PlanForm(BootstrapMixin, forms.ModelForm):
    """FORMATO FPP06 - Plan de prácticas del estudiante."""

    actividades_json = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = PlanPracticas
        fields = [
            "est_direccion", "est_telefono", "est_email",
            "emp_razon_social", "emp_direccion", "emp_ruc", "emp_telefono", "emp_email",
            "ger_nombre", "ger_telefono", "ger_email",
            "jefe_nombre", "jefe_cargo", "jefe_email",
            "areas", "fecha_inicio", "fecha_fin", "resultados_aprendizaje",
        ]
        widgets = {"fecha_inicio": FechaInput(), "fecha_fin": FechaInput(), "resultados_aprendizaje": area(4)}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["actividades_json"].widget.attrs["class"] = ""
        if not self.is_bound:
            import json
            self.initial["actividades_json"] = json.dumps(self.instance.actividades or [], ensure_ascii=False)

    def clean(self):
        import json
        d = super().clean()
        ini, fin = d.get("fecha_inicio"), d.get("fecha_fin")
        if ini and fin and fin <= ini:
            self.add_error("fecha_fin", "La fecha de término debe ser posterior a la de inicio.")
        try:
            filas = json.loads(d.get("actividades_json") or "[]")
            assert isinstance(filas, list)
        except (ValueError, AssertionError):
            raise forms.ValidationError("No se pudo leer el cronograma de actividades. Recargue la página.")
        if ini and fin:
            self.instance.fecha_inicio, self.instance.fecha_fin = ini, fin
        semanas = self.instance.semanas
        limpias = []
        for f in filas:
            texto = str(f.get("actividad", "")).strip() if isinstance(f, dict) else ""
            if not texto:
                continue
            dias = []
            for codigo in f.get("dias", []):
                try:
                    sem, dia = (int(x) for x in str(codigo).split("-"))
                except ValueError:
                    continue
                if 1 <= sem <= semanas and 1 <= dia <= 5 and f"{sem}-{dia}" not in dias:
                    dias.append(f"{sem}-{dia}")
            limpias.append({"actividad": texto[:300], "dias": sorted(dias, key=lambda c: tuple(map(int, c.split("-"))))})
        if not limpias:
            raise forms.ValidationError("Agregue al menos una actividad en la sección III.")
        sin_dias = [str(i + 1) for i, f in enumerate(limpias) if not f["dias"]]
        if sin_dias:
            raise forms.ValidationError(
                f"Marque en el cronograma los días de la(s) actividad(es) N.º {', '.join(sin_dias)}.")
        d["actividades_lista"] = limpias
        return d

    def save(self, commit=True):
        plan = super().save(commit=False)
        plan.actividades = self.cleaned_data["actividades_lista"]
        if commit:
            plan.save()
        return plan


class PlanFirmadoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PlanPracticas
        fields = ["archivo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["archivo"].required = True
        self.fields["archivo"].help_text = ("Plan FPP06 firmado por el tutor empresarial, el tutor académico "
                                            "y usted, escaneado en PDF.")


class InformeForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = InformeFinal
        fields = [
            "resumen", "actividades_realizadas", "resultados", "conclusiones",
            "horas_cumplidas", "archivo", "certificado_empresa",
        ]
        widgets = {
            "resumen": area(3), "actividades_realizadas": area(5),
            "resultados": area(4), "conclusiones": area(4),
        }


class CertificadoEmpresaForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = InformeFinal
        fields = ["certificado_empresa"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["certificado_empresa"].required = True


# ----------------------------- Revisión -----------------------------------
class TextoForm(BootstrapMixin, forms.Form):
    texto = forms.CharField(label="Comentario / observación", widget=area(3))


class DecisionSolicitudForm(BootstrapMixin, forms.Form):
    ACCIONES = [("APROBADO", "Aprobar"), ("RECHAZADO", "Rechazar"), ("DEVUELTO", "Devolver para corrección")]
    accion = forms.ChoiceField(choices=ACCIONES)
    tutor = forms.ModelChoiceField(
        queryset=Usuario.objects.none(), required=False,
        label="Docente-tutor asignado", help_text="Obligatorio al aprobar.",
    )
    observacion = forms.CharField(widget=area(3), required=False)

    def __init__(self, *args, solicitud=None, **kwargs):
        super().__init__(*args, **kwargs)
        tutores = Usuario.objects.filter(rol="TUTOR")
        if solicitud:
            del_convenio = solicitud.convenio.tutores.all()
            if del_convenio.exists():
                tutores = del_convenio
            self.initial.setdefault("tutor", solicitud.tutor_id or (tutores.first().pk if tutores else None))
        self.fields["tutor"].queryset = tutores

    def clean(self):
        d = super().clean()
        if d.get("accion") == "APROBADO" and not d.get("tutor"):
            self.add_error("tutor", "Debe asignar un docente-tutor para aprobar.")
        if d.get("accion") in ("RECHAZADO", "DEVUELTO") and not d.get("observacion"):
            self.add_error("observacion", "Indique el motivo.")
        return d


# ----------------------------- Coordinador --------------------------------
class EmpresaForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Empresa
        fields = "__all__"


class ConvenioForm(BootstrapMixin, forms.ModelForm):
    """Convenio. El tutor empresarial se elige de la lista o se registra aquí mismo."""

    te_cedula = forms.CharField(label="Cédula", required=False, max_length=10)
    te_nombres = forms.CharField(label="Nombres", required=False)
    te_apellidos = forms.CharField(label="Apellidos", required=False)
    te_correo = forms.EmailField(label="Correo", required=False)
    te_telefono = forms.CharField(label="Teléfono", required=False)
    te_cargo = forms.CharField(label="Cargo", required=False)

    CAMPOS_NUEVO_TE = ["te_cedula", "te_nombres", "te_apellidos", "te_correo", "te_telefono", "te_cargo"]

    class Meta:
        model = Convenio
        fields = [
            "codigo", "empresa", "carreras", "objeto", "cupos", "fecha_inicio", "fecha_fin", "documento", "activo",
            "rep_legal_nombre", "rep_legal_cedula", "rep_legal_cargo", "tutor_empresarial",
        ]
        labels = {"tutor_empresarial": "Tutor empresarial registrado", "codigo": "Código",
                  "fecha_inicio": "Fecha de inicio", "fecha_fin": "Fecha de fin", "documento": "Convenio firmado (PDF)"}
        widgets = {
            "fecha_inicio": FechaInput(), "fecha_fin": FechaInput(), "objeto": area(2),
            "carreras": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["carreras"].widget.attrs["class"] = "form-check-input"
        self.fields["tutor_empresarial"].queryset = Usuario.objects.filter(rol="TUTOR_EMP").select_related("empresa")
        self.fields["tutor_empresarial"].label_from_instance = (
            lambda u: f"{u.get_full_name()} — {u.empresa or 'sin empresa'} ({u.cedula})")
        self.fields["tutor_empresarial"].required = False

    def clean(self):
        d = super().clean()
        nuevo = {c: (d.get(c) or "").strip() for c in self.CAMPOS_NUEVO_TE}
        if any(nuevo.values()):
            for c in ("te_cedula", "te_nombres", "te_apellidos", "te_correo"):
                if not nuevo[c]:
                    self.add_error(c, "Obligatorio para registrar al nuevo tutor empresarial.")
            if nuevo["te_cedula"]:
                if not cedula_valida(nuevo["te_cedula"]):
                    self.add_error("te_cedula", "Cédula no válida.")
                elif Usuario.objects.filter(username=nuevo["te_cedula"]).exists():
                    self.add_error("te_cedula", "Ya existe un usuario con esta cédula: selecciónelo en la lista.")
        elif not d.get("tutor_empresarial"):
            self.add_error("tutor_empresarial", "Seleccione un tutor empresarial o registre uno nuevo abajo.")
        return d

    def save(self, commit=True):
        conv = super().save(commit=False)
        d = self.cleaned_data
        if d.get("te_cedula"):
            te = Usuario(cedula=d["te_cedula"].strip(), first_name=d["te_nombres"].strip().title(),
                         last_name=d["te_apellidos"].strip().title(), email=d["te_correo"].strip().lower(),
                         telefono=d.get("te_telefono", ""), cargo=d.get("te_cargo", ""),
                         rol=Usuario.Rol.TUTOR_EMP, empresa=conv.empresa, debe_cambiar_clave=True)
            te.set_password(te.cedula)
            te.save()
            conv.tutor_empresarial = te
            self.tutor_creado = te
        elif conv.tutor_empresarial and not conv.tutor_empresarial.empresa_id:
            conv.tutor_empresarial.empresa = conv.empresa
            conv.tutor_empresarial.save(update_fields=["empresa"])
        if commit:
            conv.save()
            self.save_m2m()
        return conv


class TutoresForm(forms.Form):
    tutores = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.filter(rol="TUTOR"), required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
    )


class ArchivoFirmadoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = CartaAceptacion
        fields = ["archivo_firmado"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["archivo_firmado"].required = True
        self.fields["archivo_firmado"].label = "Carta firmada (PDF)"


# ----------------------------- Administrador ------------------------------
class UsuarioForm(BootstrapMixin, forms.ModelForm):
    """Registro de usuario: la cédula es el usuario y la contraseña inicial."""

    class Meta:
        model = Usuario
        fields = ["cedula", "first_name", "last_name", "email", "telefono", "rol", "carrera", "empresa", "cargo",
                  "is_active"]
        labels = {"first_name": "Nombres", "last_name": "Apellidos", "email": "Correo electrónico",
                  "is_active": "Usuario activo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in ("cedula", "first_name", "last_name", "email"):
            self.fields[campo].required = True
        self.fields["cedula"].help_text = "Será el usuario para ingresar al sistema."
        if not self.instance.pk:
            self.fields["cedula"].help_text += " La contraseña inicial también será la cédula."
            del self.fields["is_active"]
        else:
            self.fields["restablecer_clave"] = forms.BooleanField(
                required=False, label="Restablecer la contraseña a la cédula",
                widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))

    def clean_cedula(self):
        cedula = self.cleaned_data["cedula"].strip()
        otros = Usuario.objects.filter(Q(username=cedula) | Q(cedula=cedula)).exclude(pk=self.instance.pk)
        if otros.exists():
            raise forms.ValidationError("Ya existe un usuario con esta cédula.")
        return cedula

    def save(self, commit=True):
        u = super().save(commit=False)
        if not u.pk or self.cleaned_data.get("restablecer_clave"):
            u.set_password(u.cedula)
            u.debe_cambiar_clave = True
        u.is_staff = u.rol == Usuario.Rol.ADMIN
        if commit:
            u.save()
        return u


class CargaMasivaForm(forms.Form):
    archivo = forms.FileField(
        label="Archivo Excel (.xlsx) o CSV",
        validators=[FileExtensionValidator(["xlsx", "csv"])],
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".xlsx,.csv"}),
    )
    actualizar = forms.BooleanField(
        required=False, label="Actualizar los datos de usuarios que ya existen (no cambia su contraseña)",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class CarreraForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Carrera
        fields = ["codigo", "nombre", "practicas_requeridas", "horas_por_practica"]
        labels = {"codigo": "Código", "practicas_requeridas": "Prácticas requeridas",
                  "horas_por_practica": "Horas por práctica"}
        help_texts = {"codigo": "Código corto que se usa en la carga masiva (ej.: TDS)."}

    def clean_codigo(self):
        return self.cleaned_data["codigo"].strip().upper()


class RespuestaCartaForm(BootstrapMixin, forms.ModelForm):
    DECISIONES = [("ACEPTADA", "Aceptar al estudiante y generar la carta de aceptación"),
                  ("NO_ACEPTADA", "No aceptar al estudiante")]
    decision = forms.ChoiceField(choices=DECISIONES, widget=forms.RadioSelect, initial="ACEPTADA")

    class Meta:
        model = CartaAceptacion
        fields = ["horario", "observacion_empresa", "archivo_aceptacion"]
        widgets = {"observacion_empresa": area(2)}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["decision"].widget.attrs["class"] = "form-check-input"

    def clean(self):
        d = super().clean()
        if d.get("decision") == "ACEPTADA" and not d.get("horario"):
            self.add_error("horario", "Indique el horario de las prácticas.")
        if d.get("decision") == "NO_ACEPTADA" and not d.get("observacion_empresa"):
            self.add_error("observacion_empresa", "Indique el motivo.")
        return d


class EvaluacionForm(forms.ModelForm):
    """Formato FPP08: una nota de 0 a 1 por aspecto."""

    class Meta:
        model = EvaluacionEmpresarial
        fields = [c for c, _, _ in ASPECTOS_FPP08]
        widgets = {c: forms.NumberInput(attrs={"class": "form-control form-control-sm nota-fpp08", "step": "0.001",
                                               "min": "0", "max": "1", "placeholder": "0.000"})
                   for c, _, _ in ASPECTOS_FPP08}


class EvaluacionFirmadaForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = EvaluacionEmpresarial
        fields = ["archivo_firmado"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["archivo_firmado"].required = True
        self.fields["archivo_firmado"].help_text = ("Escanee el formato FPP08 firmado por usted y por su tutor "
                                                    "empresarial, y súbalo en PDF.")
