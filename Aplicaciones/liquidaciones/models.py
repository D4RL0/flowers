from django.db import models
from Aplicaciones.administracion.models import Proveedor, Variedad
from Aplicaciones.postcosecha.models import Clasificacion, Tarifario
from FlorLY.file_security import validate_document


class Liquidacion(models.Model):
    ESTADOS = [
        ('PEND_DOCUMENTO', 'Pendiente de documento'),
        ('PEND_PAGO', 'Pendiente de pago'),
        ('PAGADA', 'Pagada'),
    ]

    codigo_liquidacion = models.CharField(max_length=12, primary_key=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    fecha_liquidacion = models.DateField()
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    documento_proveedor = models.FileField(
        upload_to='liquidaciones/documentos/',
        null=True,
        blank=True,
        validators=[validate_document],
    )
    estado = models.CharField(max_length=15, choices=ESTADOS, default='PEND_DOCUMENTO')
    clasificaciones = models.ManyToManyField(
        Clasificacion,
        related_name='liquidaciones',
        blank=True,
    )
    observacion = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['proveedor', 'fecha_liquidacion'],
                name='liq_unica_proveedor_fecha_cierre',
            ),
        ]

    def __str__(self):
        return f"Liquidación {self.codigo_liquidacion} - {self.proveedor}"


class DetalleLiquidacion(models.Model):
    CALIDADES = [
        ('OPTIMO', 'Óptimo'),
        ('ESTANDAR', 'Estándar'),
    ]

    liquidacion = models.ForeignKey(Liquidacion, on_delete=models.CASCADE)
    variedad = models.ForeignKey(Variedad, on_delete=models.PROTECT)
    tarifario = models.ForeignKey(Tarifario, on_delete=models.PROTECT)
    calidad = models.CharField(max_length=10, choices=CALIDADES)
    cantidad_tallos = models.PositiveIntegerField()
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=4)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.variedad.nombre} - {self.get_calidad_display()}"
