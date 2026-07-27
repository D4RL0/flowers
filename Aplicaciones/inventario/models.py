from django.db import models
from Aplicaciones.administracion.models import Finca
from Aplicaciones.administracion.validators import validar_telefono_ecuatoriano


class ProveedorInsumo(models.Model):
    codigo_proveedor_insumo = models.CharField(max_length=12, primary_key=True)
    nombre_contacto = models.CharField(max_length=200)
    nombre_empresa = models.CharField(max_length=200)
    telefono = models.CharField(max_length=15, validators=[validar_telefono_ecuatoriano])
    estado = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre_empresa

    def save(self, *args, **kwargs):
        self.nombre_contacto = self.nombre_contacto.strip().upper()
        self.nombre_empresa = self.nombre_empresa.strip().upper()
        super().save(*args, **kwargs)


class Categoria(models.Model):
    codigo_categoria = models.CharField(max_length=10, primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    estado = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.strip().upper()
        super().save(*args, **kwargs)


class UnidadMedida(models.Model):
    codigo_unidad_medida = models.CharField(max_length=10, primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    abreviatura = models.CharField(max_length=20, unique=True)
    estado = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.abreviatura

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.strip().upper()
        self.abreviatura = self.abreviatura.strip().upper()
        super().save(*args, **kwargs)


class Producto(models.Model):
    codigo_producto = models.CharField(max_length=10, primary_key=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT)
    nombre = models.CharField(max_length=150)
    marca = models.CharField(max_length=100, blank=True)
    existencia_actual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.strip().upper()
        self.marca = self.marca.strip().upper()
        super().save(*args, **kwargs)


class Entrada(models.Model):
    codigo_entrada = models.CharField(max_length=12, primary_key=True)
    proveedor_insumo = models.ForeignKey(ProveedorInsumo, on_delete=models.PROTECT)
    fecha_entrada = models.DateField()
    numero_factura = models.CharField(max_length=50, blank=True)
    observacion = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Entrada {self.codigo_entrada}"


class DetalleEntrada(models.Model):
    entrada = models.ForeignKey(Entrada, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    tipo_presentacion = models.CharField(max_length=100)
    contenido_presentacion = models.DecimalField(max_digits=12, decimal_places=2)
    cantidad_envases = models.PositiveIntegerField()
    cantidad_ingresada = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.producto.nombre} - {self.cantidad_ingresada} {self.producto.unidad_medida}"


class Salida(models.Model):
    codigo_salida = models.CharField(max_length=12, primary_key=True)
    finca = models.ForeignKey(Finca, on_delete=models.PROTECT)
    fecha_salida = models.DateField()
    destino = models.CharField(max_length=150, blank=True)
    motivo = models.CharField(max_length=200)
    observacion = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Salida {self.codigo_salida}"


class DetalleSalida(models.Model):
    salida = models.ForeignKey(Salida, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad_salida = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.producto.nombre} - {self.cantidad_salida} {self.producto.unidad_medida}"
