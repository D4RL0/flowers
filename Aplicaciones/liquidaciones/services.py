import calendar
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from Aplicaciones.administracion.models import Proveedor
from Aplicaciones.postcosecha.models import Clasificacion, Recepcion, Tarifario

from .models import DetalleLiquidacion, Liquidacion


def _fecha_mensual(fecha_base, desplazamiento_meses):
    indice = fecha_base.year * 12 + fecha_base.month - 1 + desplazamiento_meses
    anio, mes_cero = divmod(indice, 12)
    mes = mes_cero + 1
    dia = min(fecha_base.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def _generar_codigo():
    ultimo = Liquidacion.objects.select_for_update().order_by(
        '-codigo_liquidacion'
    ).values_list('codigo_liquidacion', flat=True).first()
    numero = int(ultimo[3:]) + 1 if ultimo else 1
    return f'LIQ{numero:06d}'


def fechas_ciclos_vencidos(fecha_inicial, hoy):
    """Devuelve (fecha_generacion, fecha_corte) de los ciclos ya vencidos."""
    ciclos = []
    numero = 1
    while True:
        aniversario = _fecha_mensual(fecha_inicial, numero)
        fecha_generacion = aniversario - timedelta(days=1)
        if fecha_generacion > hoy:
            break
        ciclos.append((fecha_generacion, fecha_generacion - timedelta(days=2)))
        numero += 1
    return ciclos


@transaction.atomic
def generar_liquidacion_proveedor(proveedor, fecha_generacion, fecha_corte):
    existente = Liquidacion.objects.filter(
        proveedor=proveedor,
        fecha_liquidacion=fecha_generacion,
    ).first()
    if existente:
        return existente, False

    ids_elegibles = Clasificacion.objects.filter(
            recepcion__proveedor=proveedor,
            recepcion__fecha_recepcion__date__lte=fecha_corte,
            detalleclasificacion__isnull=False,
            liquidaciones__isnull=True,
        ).values_list('pk', flat=True).distinct()
    clasificaciones = list(
        Clasificacion.objects.select_for_update(of=('self',)).filter(
            pk__in=ids_elegibles,
        ).select_related('recepcion').prefetch_related(
            'detalleclasificacion_set__detalle_recepcion__variedad'
        )
    )
    if not clasificaciones:
        return None, False

    agrupados = defaultdict(lambda: {'cantidad': 0, 'precio': Decimal('0')})
    for clasificacion in clasificaciones:
        fecha_recepcion = clasificacion.recepcion.fecha_recepcion.date()
        for detalle in clasificacion.detalleclasificacion_set.all():
            variedad = detalle.detalle_recepcion.variedad
            tarifario = Tarifario.objects.filter(
                variedad=variedad,
                fecha_inicio__lte=fecha_recepcion,
            ).filter(
                Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha_recepcion)
            ).order_by('-fecha_inicio').first()
            if not tarifario:
                raise ValueError(f'No existe tarifa vigente para {variedad.nombre}.')
            precio = tarifario.precio_optimo if detalle.largo == 'OPTIMO' else tarifario.precio_estandar
            clave = (variedad.pk, tarifario.pk, detalle.largo)
            agrupados[clave]['cantidad'] += detalle.tallos_exportables
            agrupados[clave]['precio'] = precio

    fechas = [c.recepcion.fecha_recepcion.date() for c in clasificaciones]
    liquidacion = Liquidacion.objects.create(
        codigo_liquidacion=_generar_codigo(),
        proveedor=proveedor,
        fecha_inicio=min(fechas),
        fecha_fin=fecha_corte,
        fecha_liquidacion=fecha_generacion,
        estado='PEND_DOCUMENTO',
        observacion='Generada automáticamente por cierre mensual.',
    )
    total = Decimal('0')
    for (variedad_id, tarifario_id, calidad), valores in agrupados.items():
        subtotal = valores['cantidad'] * valores['precio']
        DetalleLiquidacion.objects.create(
            liquidacion=liquidacion,
            variedad_id=variedad_id,
            tarifario_id=tarifario_id,
            calidad=calidad,
            cantidad_tallos=valores['cantidad'],
            valor_unitario=valores['precio'],
            subtotal=subtotal,
        )
        total += subtotal
    liquidacion.total = total
    liquidacion.save(update_fields=['total', 'fecha_modificacion'])
    liquidacion.clasificaciones.set(clasificaciones)
    return liquidacion, True


def generar_liquidaciones_vencidas(hoy):
    generadas = []
    errores = []
    proveedores = Proveedor.objects.filter(
        recepcion__isnull=False
    ).distinct().order_by('codigo_proveedor')
    for proveedor in proveedores:
        primera = Recepcion.objects.filter(
            proveedor=proveedor
        ).order_by('fecha_recepcion').values_list('fecha_recepcion__date', flat=True).first()
        for fecha_generacion, fecha_corte in fechas_ciclos_vencidos(primera, hoy):
            try:
                liquidacion, creada = generar_liquidacion_proveedor(
                    proveedor, fecha_generacion, fecha_corte
                )
                if creada:
                    generadas.append(liquidacion)
            except ValueError as error:
                errores.append(f'{proveedor}: {error}')
                break
    return generadas, errores
