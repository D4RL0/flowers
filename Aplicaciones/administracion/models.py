from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from .validators import validar_cedula_ecuatoriana, validar_documento_ecuatoriano, validar_telefono_ecuatoriano
from FlorLY.file_security import validate_document, validate_image


class Proveedor(models.Model):
    codigo_proveedor = models.CharField(max_length=10, primary_key=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    cedula_ruc = models.CharField(
        max_length=13,
        unique=True,
        validators=[validar_documento_ecuatoriano],
    )
    telefono = models.CharField(max_length=15, validators=[validar_telefono_ecuatoriano])
    estado = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

    def save(self, *args, **kwargs):
        self.nombres = self.nombres.strip().upper()
        self.apellidos = self.apellidos.strip().upper()
        super().save(*args, **kwargs)


class Variedad(models.Model):
    codigo_variedad = models.CharField(max_length=10, primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    imagen = models.FileField(
        upload_to='variedades/imagenes/',
        null=True,
        blank=True,
        validators=[validate_image],
    )
    estado = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.strip().upper()
        super().save(*args, **kwargs)


class Finca(models.Model):
    codigo_finca = models.CharField(max_length=10, primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    ubicacion = models.CharField(max_length=200)
    estado = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.strip().upper()
        super().save(*args, **kwargs)


class Personal(models.Model):
    codigo_personal = models.CharField(max_length=10, primary_key=True)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    cedula = models.CharField(
        max_length=10,
        unique=True,
        validators=[validar_cedula_ecuatoriana],
    )
    telefono = models.CharField(max_length=15, validators=[validar_telefono_ecuatoriano])
    fecha_ingreso = models.DateField()
    area = models.CharField(max_length=100)
    finca = models.ForeignKey(Finca, on_delete=models.PROTECT)
    estado = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"

    def save(self, *args, **kwargs):
        self.nombres = self.nombres.strip().upper()
        self.apellidos = self.apellidos.strip().upper()
        super().save(*args, **kwargs)

    @property
    def anios_completos(self):
        hoy = timezone.localdate()
        return max(0, hoy.year - self.fecha_ingreso.year - (
            (hoy.month, hoy.day) < (self.fecha_ingreso.month, self.fecha_ingreso.day)
        ))

    @property
    def dias_vacaciones_generados(self):
        return Decimal(self.anios_completos * 15)

    @property
    def dias_permisos_descontados(self):
        return self.permisos.aggregate(total=Sum('dias_descontados'))['total'] or Decimal('0')

    @property
    def dias_vacaciones_tomados(self):
        return self.vacaciones.aggregate(total=Sum('dias_tomados'))['total'] or Decimal('0')

    @property
    def saldo_vacaciones(self):
        return max(
            Decimal('0'),
            self.dias_vacaciones_generados - self.dias_vacaciones_tomados - self.dias_permisos_descontados,
        )

    @property
    def tiene_derecho_vacaciones(self):
        return self.anios_completos >= 1 and self.saldo_vacaciones > 0


class PermisoPersonal(models.Model):
    MOTIVOS = [
        ('CITA_MEDICA', 'Cita médica'),
        ('CALAMIDAD_DOMESTICA', 'Calamidad doméstica'),
        ('ASUNTOS_PARTICULARES', 'Asuntos particulares'),
        ('OTRO', 'Otro'),
    ]

    personal = models.ForeignKey(Personal, on_delete=models.CASCADE, related_name='permisos')
    motivo = models.CharField(max_length=30, choices=MOTIVOS)
    observacion = models.TextField(blank=True)
    fecha_desde = models.DateField()
    fecha_hasta = models.DateField()
    hora_salida = models.TimeField(null=True, blank=True)
    hora_retorno = models.TimeField(null=True, blank=True)
    dias_descontados = models.DecimalField(max_digits=7, decimal_places=2)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Permiso de {self.personal} - {self.get_motivo_display()}"

    @property
    def descuento_legible(self):
        if self.hora_salida and self.hora_retorno:
            minutos_totales = int(self.dias_descontados * Decimal('480'))
            horas, minutos = divmod(minutos_totales, 60)
            partes = []
            if horas:
                partes.append(f'{horas} {"hora" if horas == 1 else "horas"}')
            if minutos:
                partes.append(f'{minutos} min')
            return ' '.join(partes) or '0 horas'
        return f'{self.dias_descontados} {"día" if self.dias_descontados == 1 else "días"}'


class VacacionPersonal(models.Model):
    personal = models.ForeignKey(Personal, on_delete=models.CASCADE, related_name='vacaciones')
    fecha_desde = models.DateField()
    fecha_hasta = models.DateField()
    dias_tomados = models.PositiveIntegerField()
    observacion = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Vacaciones de {self.personal}: {self.fecha_desde} - {self.fecha_hasta}"


class DocumentoPersonal(models.Model):
    personal = models.ForeignKey(Personal, on_delete=models.CASCADE, related_name='documentos')
    nombre = models.CharField(max_length=150)
    archivo = models.FileField(upload_to='personal/documentos/', validators=[validate_document])
    observacion = models.TextField(blank=True)
    fecha_documento = models.DateField(default=timezone.localdate)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} - {self.personal}"
