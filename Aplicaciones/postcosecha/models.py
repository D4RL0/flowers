from django.db import models
from Aplicaciones.administracion.models import Finca, Personal, Proveedor, Variedad


class Recepcion(models.Model):
    codigo_recepcion = models.CharField(max_length=12, primary_key=True)
    numero_recepcion = models.PositiveIntegerField(unique=True)
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    finca = models.ForeignKey(
        Finca,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    empleado_receptor = models.ForeignKey(
        Personal,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='recepciones_realizadas',
    )
    fecha_recepcion = models.DateTimeField()
    observacion = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Recepción N.° {self.numero_recepcion}"


    @property
    def total_tallos(self):
        return sum(detalle.total_tallos for detalle in self.detallerecepcion_set.all())


class DetalleRecepcion(models.Model):
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_CLASIFICACION', 'En clasificación'),
        ('CLASIFICADA', 'Clasificada'),
    ]

    recepcion = models.ForeignKey(Recepcion, on_delete=models.CASCADE)
    variedad = models.ForeignKey(Variedad, on_delete=models.PROTECT)
    cantidad_mallas = models.PositiveIntegerField()
    tallos_por_malla = models.PositiveIntegerField(default=1)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')

    @property
    def total_tallos(self):
        return self.cantidad_mallas * self.tallos_por_malla

    def __str__(self):
        return f"{self.variedad.nombre} - {self.cantidad_mallas} mallas"


class Clasificacion(models.Model):
    codigo_clasificacion = models.CharField(max_length=12, primary_key=True)
    recepcion = models.OneToOneField(
        Recepcion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='clasificacion',
    )
    fecha_clasificacion = models.DateField()
    observacion = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Clasificación {self.codigo_clasificacion}"


class DetalleClasificacion(models.Model):
    LARGOS = [
        ('OPTIMO', 'Óptimo'),
        ('ESTANDAR', 'Estándar'),
    ]

    clasificacion = models.ForeignKey(Clasificacion, on_delete=models.CASCADE)
    detalle_recepcion = models.ForeignKey(DetalleRecepcion, on_delete=models.PROTECT)
    cantidad_mallas_procesadas = models.PositiveIntegerField()
    largo = models.CharField(max_length=10, choices=LARGOS)
    tallos_exportables = models.PositiveIntegerField()
    tallos_nacionales = models.PositiveIntegerField(default=0)
    tallos_sobrantes = models.PositiveIntegerField(default=0)
    observacion = models.TextField(blank=True)

    def __str__(self):
        return f"{self.detalle_recepcion.variedad.nombre} - {self.get_largo_display()}"


class Tarifario(models.Model):
    codigo_tarifario = models.CharField(max_length=12, primary_key=True)
    variedad = models.ForeignKey(Variedad, on_delete=models.PROTECT)
    precio_optimo = models.DecimalField(max_digits=10, decimal_places=4)
    precio_estandar = models.DecimalField(max_digits=10, decimal_places=4)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    estado = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Tarifario de {self.variedad.nombre}"
