from django.db import models
from django.conf import settings


class Bitacora(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    accion = models.CharField(max_length=100)
    tabla_afectada = models.CharField(max_length=100)
    codigo_registro = models.CharField(max_length=20)
    descripcion = models.TextField(blank=True)
    direccion_ip = models.GenericIPAddressField(null=True, blank=True)
    metodo = models.CharField(max_length=10, blank=True)
    ruta = models.CharField(max_length=255, blank=True)
    resultado = models.CharField(max_length=20, default='REGISTRADA')
    datos_anteriores = models.JSONField(null=True, blank=True)
    datos_nuevos = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.usuario} - {self.accion} - {self.fecha_hora}"
