import uuid
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .validadores import validar_cedula

solo_pdf = FileExtensionValidator(["pdf"])
pdf_o_word = FileExtensionValidator(["pdf", "doc", "docx"])


# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------
class Carrera(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=150)
    practicas_requeridas = models.PositiveSmallIntegerField(
        default=2, help_text="Número de prácticas que el estudiante debe culminar para graduarse."
    )
    horas_por_practica = models.PositiveIntegerField(default=240)
    # Asignación de docentes tutores por carrera (la realiza el coordinador)
    tutores = models.ManyToManyField(
        "Usuario", blank=True, related_name="carreras_tutoria",
        limit_choices_to={"rol": "TUTOR"},
    )

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


# ---------------------------------------------------------------------------
# Usuarios y roles
# ---------------------------------------------------------------------------
class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        COORDINADOR = "COORDINADOR", "Docente-coordinador"
        TUTOR = "TUTOR", "Docente-tutor"
        ESTUDIANTE = "ESTUDIANTE", "Estudiante"
        RECTOR = "RECTOR", "Rector"
        TUTOR_EMP = "TUTOR_EMP", "Tutor empresarial"

    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.ESTUDIANTE)
    # La cédula es también el nombre de usuario para ingresar al sistema
    cedula = models.CharField("Cédula", max_length=10, blank=True, validators=[validar_cedula])
    telefono = models.CharField("Teléfono", max_length=20, blank=True)
    carrera = models.ForeignKey(
        Carrera, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="usuarios", help_text="Carrera del estudiante, tutor o coordinador.",
    )
    # Datos del tutor empresarial
    empresa = models.ForeignKey(
        "Empresa", null=True, blank=True, on_delete=models.SET_NULL, related_name="tutores_empresariales",
        help_text="Solo para tutores empresariales.",
    )
    cargo = models.CharField(max_length=100, blank=True, help_text="Cargo en la empresa (tutor empresarial).")
    debe_cambiar_clave = models.BooleanField(
        default=False, help_text="Obliga a cambiar la contraseña en el próximo ingreso."
    )

    class Meta:
        ordering = ["last_name", "first_name"]

    def save(self, *args, **kwargs):
        if self.cedula:
            self.username = self.cedula
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def es_admin(self):
        return self.rol == self.Rol.ADMIN or self.is_superuser

    def tiene_rol(self, *roles):
        return self.es_admin or self.rol in roles


# ---------------------------------------------------------------------------
# Convenios
# ---------------------------------------------------------------------------
class Empresa(models.Model):
    ruc = models.CharField("RUC", max_length=13, unique=True)
    nombre = models.CharField("Razón social", max_length=200)
    tipo = models.CharField(
        max_length=20,
        choices=[("PUBLICA", "Pública"), ("PRIVADA", "Privada"), ("ONG", "ONG / Otra")],
        default="PRIVADA",
    )
    direccion = models.CharField(max_length=250, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    correo = models.EmailField(help_text="Correo al que se envían las cartas de aceptación.")

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Convenio(models.Model):
    codigo = models.CharField(max_length=30, unique=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name="convenios")
    carreras = models.ManyToManyField(Carrera, related_name="convenios")
    objeto = models.TextField("Objeto del convenio", blank=True)
    cupos = models.PositiveIntegerField(default=5)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    documento = models.FileField(upload_to="convenios/", blank=True, validators=[solo_pdf])
    activo = models.BooleanField(default=True)

    # Cada convenio tiene representante legal y tutor empresarial
    rep_legal_nombre = models.CharField("Representante legal", max_length=150)
    rep_legal_cedula = models.CharField("Cédula del representante", max_length=13, blank=True)
    rep_legal_cargo = models.CharField("Cargo del representante", max_length=100, blank=True)
    tutor_empresarial = models.ForeignKey(
        Usuario, null=True, blank=True, on_delete=models.SET_NULL, related_name="convenios_empresa",
        limit_choices_to={"rol": "TUTOR_EMP"},
    )

    # Asignación de docentes tutores al convenio (la realiza el coordinador)
    tutores = models.ManyToManyField(
        Usuario, blank=True, related_name="convenios_tutoria",
        limit_choices_to={"rol": "TUTOR"},
    )

    class Meta:
        ordering = ["-fecha_inicio"]

    def __str__(self):
        return f"{self.codigo} - {self.empresa}"

    @property
    def vigente(self):
        hoy = timezone.localdate()
        return self.activo and self.fecha_inicio <= hoy <= self.fecha_fin

    # Atajos usados en pantallas y PDF
    @property
    def tutor_emp_nombre(self):
        return str(self.tutor_empresarial) if self.tutor_empresarial else "Por asignar"

    @property
    def tutor_emp_cargo(self):
        return self.tutor_empresarial.cargo if self.tutor_empresarial else ""

    @property
    def tutor_emp_correo(self):
        return self.tutor_empresarial.email if self.tutor_empresarial else ""


# ---------------------------------------------------------------------------
# Flujo de la práctica
# ---------------------------------------------------------------------------
class Solicitud(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"
        DEVUELTO = "DEVUELTO", "Devuelto"

    estudiante = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="solicitudes")
    convenio = models.ForeignKey(Convenio, on_delete=models.PROTECT, related_name="solicitudes")
    numero_practica = models.PositiveSmallIntegerField("N.º de práctica", default=1)
    area = models.CharField("Área / departamento", max_length=150)
    fecha_inicio = models.DateField("Fecha de inicio propuesta")
    fecha_fin = models.DateField("Fecha de fin propuesta")
    horas = models.PositiveIntegerField(default=240)
    motivo = models.TextField("Justificación")
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    observacion = models.TextField("Observación del coordinador", blank=True)
    tutor = models.ForeignKey(
        Usuario, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="solicitudes_tutor", limit_choices_to={"rol": "TUTOR"},
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"Práctica {self.numero_practica} - {self.estudiante} ({self.convenio.empresa})"

    @property
    def editable(self):
        """El estudiante solo puede modificar/eliminar si está pendiente o devuelta."""
        return self.estado in (self.Estado.PENDIENTE, self.Estado.DEVUELTO)


class PlanPracticas(models.Model):
    """FORMATO FPP06 - Plan de prácticas del estudiante."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "En revisión"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    MAX_SEMANAS = 16

    solicitud = models.OneToOneField(Solicitud, on_delete=models.CASCADE, related_name="plan")

    # I. Datos del estudiante (nombres y cédula se toman del usuario)
    est_direccion = models.CharField("Dirección", max_length=200)
    est_telefono = models.CharField("Teléfono", max_length=20)
    est_email = models.EmailField("E-mail")

    # II. Datos de la empresa
    emp_razon_social = models.CharField("Razón social", max_length=250)
    emp_direccion = models.CharField("Dirección", max_length=250)
    emp_ruc = models.CharField("RUC N.º", max_length=13, blank=True)
    emp_telefono = models.CharField("Teléfono", max_length=30, blank=True)
    emp_email = models.EmailField("E-mail", blank=True)
    ger_nombre = models.CharField("Gerente / Representante", max_length=150)
    ger_telefono = models.CharField("Teléfono", max_length=30, blank=True)
    ger_email = models.EmailField("E-mail", blank=True)
    jefe_nombre = models.CharField("Jefe inmediato", max_length=150)
    jefe_cargo = models.CharField("Cargo", max_length=100, blank=True)
    jefe_email = models.EmailField("E-mail", blank=True)
    areas = models.CharField("Área(s) donde se realiza la práctica", max_length=250)
    fecha_inicio = models.DateField("Fecha de inicio")
    fecha_fin = models.DateField("Fecha de término")
    resultados_aprendizaje = models.TextField(
        "Resultados de aprendizaje", help_text="Tomados del plan de prácticas del docente tutor.")

    # III. Actividades: [{"actividad": "...", "dias": ["1-1", "1-2", ...]}]  ("semana-día", día 1=lunes … 5=viernes)
    actividades = models.JSONField(default=list, blank=True)

    archivo = models.FileField("Plan firmado (PDF)", upload_to="planes/", blank=True, validators=[solo_pdf])
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Plan - {self.solicitud}"

    @property
    def editable(self):
        return self.estado != self.Estado.APROBADO

    @property
    def semanas(self):
        """Número de semanas del cronograma según las fechas (mínimo 4, máximo MAX_SEMANAS)."""
        if not self.fecha_inicio or not self.fecha_fin:
            return 8
        dias = (self.fecha_fin - self.fecha_inicio).days + self.fecha_inicio.weekday() + 1
        return max(4, min(self.MAX_SEMANAS, -(-dias // 7)))


class ComentarioPlan(models.Model):
    plan = models.ForeignKey(PlanPracticas, on_delete=models.CASCADE, related_name="comentarios")
    autor = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    texto = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha"]


class InformeFinal(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "En revisión"
        CORRECCION = "CORRECCION", "Con observaciones"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    solicitud = models.OneToOneField(Solicitud, on_delete=models.CASCADE, related_name="informe")
    resumen = models.TextField("Resumen ejecutivo")
    actividades_realizadas = models.TextField()
    resultados = models.TextField("Resultados y aprendizajes")
    conclusiones = models.TextField("Conclusiones y recomendaciones")
    horas_cumplidas = models.PositiveIntegerField()
    archivo = models.FileField("Informe (PDF/Word)", upload_to="informes/", blank=True, validators=[pdf_o_word])
    certificado_empresa = models.FileField(
        "Certificado de culminación emitido por la empresa (PDF)",
        upload_to="certificados_empresa/", blank=True, validators=[solo_pdf],
    )
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    version = models.PositiveSmallIntegerField(default=1)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Informe final - {self.solicitud}"

    @property
    def editable(self):
        return self.estado in (self.Estado.PENDIENTE, self.Estado.CORRECCION, self.Estado.RECHAZADO)


class ObservacionInforme(models.Model):
    informe = models.ForeignKey(InformeFinal, on_delete=models.CASCADE, related_name="observaciones")
    autor = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    texto = models.TextField("Corrección solicitada")
    version = models.PositiveSmallIntegerField(default=1)
    atendida = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]


class CartaAceptacion(models.Model):
    """Solicitud de carta de aceptación (firmada por el Rector) y la carta de aceptación
    que genera el tutor empresarial."""

    class Estado(models.TextChoices):
        POR_FIRMAR = "POR_FIRMAR", "Por firmar (Rector)"
        FIRMADA = "FIRMADA", "Firmada, por enviar"
        ENVIADA = "ENVIADA", "Enviada al tutor empresarial"
        ACEPTADA = "ACEPTADA", "Aceptada por la empresa"
        NO_ACEPTADA = "NO_ACEPTADA", "No aceptada por la empresa"

    solicitud = models.OneToOneField(Solicitud, on_delete=models.CASCADE, related_name="carta")
    numero = models.CharField(max_length=30, unique=True)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.POR_FIRMAR)
    # 1) Solicitud firmada por el Rector
    archivo_firmado = models.FileField("Solicitud firmada (PDF)", upload_to="cartas/", blank=True,
                                       validators=[solo_pdf])
    fecha_envio = models.DateTimeField(null=True, blank=True)
    enviada_a = models.EmailField(blank=True)
    # 2) Respuesta del tutor empresarial
    horario = models.CharField("Horario de prácticas", max_length=120, blank=True,
                               help_text="Ej.: Lunes a viernes de 08:00 a 13:00")
    observacion_empresa = models.TextField("Observación", blank=True)
    archivo_aceptacion = models.FileField(
        "Carta de aceptación firmada (PDF, opcional)", upload_to="cartas_aceptacion/", blank=True,
        validators=[solo_pdf], help_text="Si no se adjunta, se usa la carta generada por el sistema.",
    )
    respondida_por = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name="cartas_respondidas")
    fecha_respuesta = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Carta {self.numero}"

    @property
    def aceptada(self):
        return self.estado == self.Estado.ACEPTADA


class Certificado(models.Model):
    """Los 3 certificados distintos del sistema."""

    class Tipo(models.TextChoices):
        APROBACION = "APROBACION", "Certificado de aprobación de prácticas"          # Docente-tutor
        CULMINACION = "CULMINACION", "Certificado de culminación de prácticas"     # Docente-coordinador
        FINAL = "FINAL", "Certificado final de prácticas preprofesionales"         # Rector

    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    codigo = models.CharField(max_length=40, unique=True, editable=False)
    estudiante = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="certificados")
    # APROBACION y CULMINACION son por práctica; FINAL es por estudiante (sin solicitud)
    solicitud = models.ForeignKey(
        Solicitud, null=True, blank=True, on_delete=models.CASCADE, related_name="certificados"
    )
    emitido_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="certificados_emitidos")
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-fecha"]
        constraints = [
            models.UniqueConstraint(fields=["tipo", "solicitud"], name="un_cert_por_tipo_y_practica"),
        ]

    def save(self, *args, **kwargs):
        if not self.codigo:
            prefijo = {"APROBACION": "APR", "CULMINACION": "CUL", "FINAL": "FIN"}[self.tipo]
            self.codigo = f"ISTAM-{prefijo}-{timezone.now():%Y}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.estudiante} ({self.codigo})"


# ---------------------------------------------------------------------------
# FORMATO FPP08 - Evaluación del desempeño por el tutor empresarial
# ---------------------------------------------------------------------------
ASPECTOS_FPP08 = [
    # (campo, grupo, texto)
    ("tec_1", "TÉCNICO", "Los conocimientos del estudiante aseguran una exitosa realización de los trabajos"),
    ("tec_2", "TÉCNICO", "Tiene la habilidad para evaluar datos y tomar decisiones lógicas de manera imparcial "
                         "y desde un punto de vista racional"),
    ("tec_3", "TÉCNICO", "Es creativo y propone soluciones y/o alternativas para mejorar situaciones del trabajo"),
    ("tec_4", "TÉCNICO", "Planifica y organiza de manera adecuada el trabajo diario"),
    ("tec_5", "TÉCNICO", "Demuestra criterio profesional en la realización de sus trabajos"),
    ("tec_6", "TÉCNICO", "Su actitud es proactiva y facilita la tarea en equipo"),
    ("soc_1", "SOCIAL", "Es puntual en el trabajo"),
    ("soc_2", "SOCIAL", "Es respetuoso con el tutor empresarial y compañeros del trabajo."),
    ("soc_3", "SOCIAL", "Demuestra ser cuidadoso en su presentación personal"),
    ("soc_4", "SOCIAL", "Demuestra un alto grado de compromiso en la realización de sus tareas"),
]

# (clave, etiqueta, mínimo, máximo)
NIVELES_FPP08 = [
    ("EXCELENTE", "EXCELENTE", Decimal("0.95"), Decimal("1")),
    ("MUY_BUENO", "MUY BUENO", Decimal("0.85"), Decimal("0.949")),
    ("BUENO", "BUENO", Decimal("0.70"), Decimal("0.849")),
    ("REGULAR", "REGULAR", Decimal("0.00"), Decimal("0.699")),
]


def nivel_fpp08(valor):
    """Devuelve la clave del nivel de desempeño según la nota (0 a 1)."""
    if valor is None:
        return None
    if valor >= Decimal("0.95"):
        return "EXCELENTE"
    if valor >= Decimal("0.85"):
        return "MUY_BUENO"
    if valor >= Decimal("0.70"):
        return "BUENO"
    return "REGULAR"


def _nota():
    return models.DecimalField(max_digits=4, decimal_places=3,
                               validators=[MinValueValidator(0), MaxValueValidator(1)])


class EvaluacionEmpresarial(models.Model):
    """Formato FPP08: la llena el tutor empresarial; el estudiante sube el documento firmado."""

    solicitud = models.OneToOneField(Solicitud, on_delete=models.CASCADE, related_name="evaluacion")
    evaluador = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="evaluaciones_realizadas")
    tec_1 = _nota()
    tec_2 = _nota()
    tec_3 = _nota()
    tec_4 = _nota()
    tec_5 = _nota()
    tec_6 = _nota()
    soc_1 = _nota()
    soc_2 = _nota()
    soc_3 = _nota()
    soc_4 = _nota()
    archivo_firmado = models.FileField(
        "Evaluación firmada (PDF)", upload_to="evaluaciones/", blank=True, validators=[solo_pdf])
    fecha_subida = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Evaluación FPP08 - {self.solicitud}"

    @property
    def notas(self):
        return [(campo, grupo, texto, getattr(self, campo)) for campo, grupo, texto in ASPECTOS_FPP08]

    @property
    def nota_final(self):
        return sum((getattr(self, c) or Decimal(0)) for c, _, _ in ASPECTOS_FPP08)

    @property
    def subtotales(self):
        tot = {n[0]: Decimal(0) for n in NIVELES_FPP08}
        for c, _, _ in ASPECTOS_FPP08:
            v = getattr(self, c)
            if v is not None:
                tot[nivel_fpp08(v)] += v
        return tot

    @property
    def editable(self):
        """El tutor empresarial puede corregirla mientras el estudiante no suba la versión firmada."""
        return not self.archivo_firmado
