from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from Aplicaciones.administracion.models import Personal, Proveedor, Variedad
from Aplicaciones.liquidaciones.services import generar_liquidaciones_vencidas
from Aplicaciones.postcosecha.models import (
    Clasificacion, DetalleClasificacion, DetalleRecepcion, Recepcion, Tarifario,
)


MARCA = 'PRUEBA AUTOMÁTICA LIQUIDACIÓN 2026-07-26'


class Command(BaseCommand):
    help = 'Carga datos demostrativos identificables para probar el cierre mensual.'

    @transaction.atomic
    def handle(self, *args, **options):
        if Recepcion.objects.filter(observacion=MARCA).exists():
            raise CommandError('Los datos de prueba ya fueron cargados.')

        proveedores = list(Proveedor.objects.filter(estado=True).order_by('codigo_proveedor')[:2])
        variedades = list(Variedad.objects.filter(estado=True).order_by('codigo_variedad')[:3])
        empleado = Personal.objects.filter(estado=True, area__icontains='POSTCOSECHA').first()
        if len(proveedores) < 2 or len(variedades) < 3 or not empleado:
            raise CommandError('Se requieren 2 proveedores, 3 variedades y 1 empleado de Postcosecha.')

        for indice, variedad in enumerate(variedades, start=1):
            Tarifario.objects.create(
                codigo_tarifario=f'TAR{indice:06d}',
                variedad=variedad,
                precio_optimo=Decimal('0.22') + Decimal(indice) / 100,
                precio_estandar=Decimal('0.16') + Decimal(indice) / 100,
                fecha_inicio=date(2026, 6, 1),
            )

        fechas = [date(2026, 6, 27), date(2026, 7, 5), date(2026, 7, 14), date(2026, 7, 24)]
        numero = 1
        for proveedor_indice, proveedor in enumerate(proveedores):
            for fecha_indice, fecha in enumerate(fechas):
                momento = timezone.make_aware(datetime.combine(fecha, time(10, 0)))
                recepcion = Recepcion.objects.create(
                    codigo_recepcion=f'REC{numero:06d}',
                    numero_recepcion=numero,
                    proveedor=proveedor,
                    empleado_receptor=empleado,
                    fecha_recepcion=momento,
                    observacion=MARCA,
                )
                clasificacion = Clasificacion.objects.create(
                    codigo_clasificacion=f'CLA{numero:06d}',
                    recepcion=recepcion,
                    fecha_clasificacion=fecha + timedelta(days=1),
                    observacion=MARCA,
                )
                for variedad_indice in range(2):
                    variedad = variedades[(proveedor_indice + fecha_indice + variedad_indice) % len(variedades)]
                    mallas = 3 + fecha_indice + variedad_indice
                    tallos_malla = 25
                    detalle = DetalleRecepcion.objects.create(
                        recepcion=recepcion,
                        variedad=variedad,
                        cantidad_mallas=mallas,
                        tallos_por_malla=tallos_malla,
                        estado='CLASIFICADA',
                    )
                    total = detalle.total_tallos
                    nacionales = total // 10
                    sobrantes = total % 7
                    exportables = total - nacionales - sobrantes
                    optimos = exportables * 60 // 100
                    estandar = exportables - optimos
                    DetalleClasificacion.objects.create(
                        clasificacion=clasificacion,
                        detalle_recepcion=detalle,
                        cantidad_mallas_procesadas=mallas,
                        largo='OPTIMO',
                        tallos_exportables=optimos,
                        tallos_nacionales=nacionales,
                        tallos_sobrantes=sobrantes,
                        observacion=MARCA,
                    )
                    DetalleClasificacion.objects.create(
                        clasificacion=clasificacion,
                        detalle_recepcion=detalle,
                        cantidad_mallas_procesadas=0,
                        largo='ESTANDAR',
                        tallos_exportables=estandar,
                        observacion=MARCA,
                    )
                numero += 1

        generadas, errores = generar_liquidaciones_vencidas(date(2026, 7, 26))
        if errores:
            raise CommandError(' | '.join(errores))
        self.stdout.write(self.style.SUCCESS(
            f'Prueba cargada: {numero - 1} recepciones, {numero - 1} clasificaciones '
            f'y {len(generadas)} liquidaciones.'
        ))
