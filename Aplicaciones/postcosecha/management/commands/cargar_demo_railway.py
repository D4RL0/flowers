import random
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from Aplicaciones.administracion.models import Finca, Personal, Proveedor, Variedad
from Aplicaciones.liquidaciones.services import generar_liquidaciones_vencidas
from Aplicaciones.postcosecha.models import (
    Clasificacion,
    DetalleClasificacion,
    DetalleRecepcion,
    Recepcion,
    Tarifario,
)


MARCA = 'DEMO RAILWAY DESDE 29-06-2026'
FECHA_BASE = date(2026, 6, 29)
FECHA_CIERRE = date(2026, 7, 28)


def siguiente_codigo(modelo, campo, prefijo):
    mayor = 0
    for valor in modelo.objects.values_list(campo, flat=True):
        coincidencia = re.fullmatch(rf'{re.escape(prefijo)}(\d+)', str(valor))
        if coincidencia:
            mayor = max(mayor, int(coincidencia.group(1)))
    return f'{prefijo}{mayor + 1:06d}'


def tarifa_vigente(variedad, fecha):
    return Tarifario.objects.filter(
        variedad=variedad,
        fecha_inicio__lte=fecha,
    ).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
    ).exists()


class Command(BaseCommand):
    help = 'Carga una demostracion realista de postcosecha y liquidaciones en Railway.'

    @transaction.atomic
    def handle(self, *args, **options):
        if Recepcion.objects.filter(observacion=MARCA).exists():
            self.stdout.write(self.style.WARNING(
                'La demostracion de Railway ya existe; no se duplicaron datos.'
            ))
            return

        proveedores = list(
            Proveedor.objects.filter(estado=True).order_by('codigo_proveedor')[:4]
        )
        variedades = list(
            Variedad.objects.filter(estado=True).order_by('codigo_variedad')[:6]
        )
        empleados = list(
            Personal.objects.filter(estado=True).filter(
                Q(area__icontains='POSTCOSECHA') | Q(area__icontains='POST COSECHA')
            )
            .order_by('codigo_personal')[:3]
        )
        fincas = list(Finca.objects.filter(estado=True).order_by('codigo_finca')[:2])

        if len(proveedores) < 2:
            raise CommandError('Se necesitan al menos 2 proveedores activos.')
        if len(variedades) < 3:
            raise CommandError('Se necesitan al menos 3 variedades activas.')
        if len(empleados) < 3:
            raise CommandError('Se necesitan 3 empleados activos del area Postcosecha.')
        if not fincas:
            raise CommandError('Se necesita al menos 1 finca activa.')

        azar = random.Random(29062026)

        # Solo se crean precios cuando no existe uno que cubra el inicio del periodo.
        for indice, variedad in enumerate(variedades):
            if tarifa_vigente(variedad, FECHA_BASE):
                continue
            siguiente = Tarifario.objects.filter(
                variedad=variedad,
                fecha_inicio__gt=FECHA_BASE,
            ).order_by('fecha_inicio').first()
            Tarifario.objects.create(
                codigo_tarifario=siguiente_codigo(Tarifario, 'codigo_tarifario', 'TAR'),
                variedad=variedad,
                precio_optimo=Decimal('0.22') + Decimal(indice % 4) * Decimal('0.01'),
                precio_estandar=Decimal('0.16') + Decimal(indice % 3) * Decimal('0.01'),
                fecha_inicio=date(2026, 6, 1),
                fecha_fin=siguiente.fecha_inicio - timedelta(days=1) if siguiente else None,
                estado=siguiente is None,
            )

        fechas_proveedor = [
            date(2026, 6, 29), date(2026, 7, 3), date(2026, 7, 8),
            date(2026, 7, 15), date(2026, 7, 22), date(2026, 7, 25),
        ]
        fechas_finca = [date(2026, 7, 1), date(2026, 7, 10), date(2026, 7, 17), date(2026, 7, 24)]

        planes = []
        for proveedor in proveedores:
            # Todos empiezan el 29/06; luego se escogen cuatro fechas adicionales.
            fechas = [FECHA_BASE] + sorted(azar.sample(fechas_proveedor[1:], 4))
            planes.extend((fecha, proveedor, None) for fecha in fechas)
        for indice, fecha in enumerate(fechas_finca):
            planes.append((fecha, None, fincas[indice % len(fincas)]))
        planes.sort(key=lambda item: (item[0], str(item[1] or item[2])))

        ultimo_numero = Recepcion.objects.order_by('-numero_recepcion').values_list(
            'numero_recepcion', flat=True
        ).first() or 0
        creadas = 0
        for fecha_recepcion, proveedor, finca in planes:
            semana = (fecha_recepcion - FECHA_BASE).days // 7
            empleado = empleados[semana % 3]
            ultimo_numero += 1
            momento = timezone.make_aware(datetime.combine(
                fecha_recepcion,
                time(hour=azar.choice([8, 9, 10, 11, 13, 14]), minute=azar.choice([0, 15, 30, 45])),
            ))
            recepcion = Recepcion.objects.create(
                codigo_recepcion=siguiente_codigo(Recepcion, 'codigo_recepcion', 'REC'),
                numero_recepcion=ultimo_numero,
                proveedor=proveedor,
                finca=finca,
                empleado_receptor=empleado,
                fecha_recepcion=momento,
                observacion=MARCA,
            )

            cantidad_variedades = azar.randint(2, min(4, len(variedades)))
            elegidas = azar.sample(variedades, cantidad_variedades)
            mallas_restantes = azar.randint(24, 50)
            detalles = []
            for posicion, variedad in enumerate(elegidas):
                pendientes = len(elegidas) - posicion - 1
                if pendientes == 0:
                    mallas = mallas_restantes
                else:
                    maximo = mallas_restantes - pendientes
                    mallas = azar.randint(1, maximo)
                mallas_restantes -= mallas
                detalles.append(DetalleRecepcion.objects.create(
                    recepcion=recepcion,
                    variedad=variedad,
                    cantidad_mallas=mallas,
                    tallos_por_malla=azar.choice([20, 25, 30, 35, 40]),
                    estado='CLASIFICADA',
                ))

            fecha_clasificacion = fecha_recepcion + timedelta(days=azar.choice([0, 1, 2]))
            if fecha_clasificacion.weekday() == 6:
                fecha_clasificacion += timedelta(days=1)
            clasificacion = Clasificacion.objects.create(
                codigo_clasificacion=siguiente_codigo(
                    Clasificacion, 'codigo_clasificacion', 'CLA'
                ),
                recepcion=recepcion,
                fecha_clasificacion=fecha_clasificacion,
                observacion=MARCA,
            )

            for detalle in detalles:
                declarado = detalle.total_tallos
                faltantes = azar.randint(0, min(12, declarado // 20))
                contabilizados = declarado - faltantes
                nacionales = round(contabilizados * azar.uniform(0.06, 0.14))
                sobrantes = azar.randint(0, min(8, max(0, contabilizados - nacionales)))
                exportables = contabilizados - nacionales - sobrantes
                optimos = round(exportables * azar.uniform(0.55, 0.72))
                estandar = exportables - optimos

                DetalleClasificacion.objects.create(
                    clasificacion=clasificacion,
                    detalle_recepcion=detalle,
                    cantidad_mallas_procesadas=detalle.cantidad_mallas,
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
            creadas += 1

        liquidaciones, errores = generar_liquidaciones_vencidas(FECHA_CIERRE)
        if errores:
            raise CommandError('No se guardo la carga: ' + ' | '.join(errores))

        self.stdout.write(self.style.SUCCESS(
            f'Demostracion cargada: {creadas} recepciones y clasificaciones; '
            f'{len(liquidaciones)} liquidaciones generadas. '
            f'Empleados rotados: {", ".join(str(e) for e in empleados)}.'
        ))
