from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from Aplicaciones.liquidaciones.models import Liquidacion
from Aplicaciones.liquidaciones.services import generar_liquidaciones_vencidas
from Aplicaciones.postcosecha.models import DetalleRecepcion, Tarifario
from FlorLY.file_security import validate_and_secure_document


def inicioLiquidacion(request):
    liquidaciones = Liquidacion.objects.select_related('proveedor').prefetch_related(
        'detalleliquidacion_set__variedad'
    ).order_by('-fecha_liquidacion', '-codigo_liquidacion')
    return render(request, 'liquidaciones/inicioLiquidacion.html', {'liquidaciones': liquidaciones})


def nuevaLiquidacion(request):
    return render(request, 'liquidaciones/nuevaLiquidacion.html')


@require_POST
def guardarLiquidacion(request):
    generadas, errores = generar_liquidaciones_vencidas(timezone.localdate())
    if generadas:
        messages.success(request, f'Se generaron {len(generadas)} reporte(s) mensual(es).')
    elif not errores:
        messages.info(request, 'No existen cierres mensuales pendientes para generar.')
    for error in errores:
        messages.error(request, error)
    return redirect('inicioLiquidacion')


def verLiquidacion(request, codigo):
    liquidacion = get_object_or_404(Liquidacion.objects.select_related('proveedor'), pk=codigo)
    materiales = DetalleRecepcion.objects.filter(
        recepcion__clasificacion__liquidaciones=liquidacion,
    ).select_related('recepcion', 'variedad').prefetch_related('detalleclasificacion_set').distinct()
    filas = defaultdict(lambda: {
        'mallas': 0, 'tallos_recibidos': 0, 'optimos': 0, 'estandar': 0,
        'nacionales': 0, 'sobrantes': 0,
    })
    for material in materiales:
        fecha = material.recepcion.fecha_recepcion.date()
        fila = filas[(fecha, material.variedad_id)]
        fila['fecha'] = fecha
        fila['variedad'] = material.variedad.nombre
        fila['mallas'] += material.cantidad_mallas
        fila['tallos_recibidos'] += material.total_tallos
        for resultado in material.detalleclasificacion_set.all():
            calidad = 'optimos' if resultado.largo == 'OPTIMO' else 'estandar'
            fila[calidad] += resultado.tallos_exportables
            fila['nacionales'] += resultado.tallos_nacionales
            fila['sobrantes'] += resultado.tallos_sobrantes

    filas_reporte = []
    totales = defaultdict(lambda: Decimal('0'))
    for (_, variedad_id), fila in sorted(filas.items()):
        tarifario = Tarifario.objects.filter(
            variedad_id=variedad_id, fecha_inicio__lte=fila['fecha'],
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fila['fecha'])
        ).order_by('-fecha_inicio').first()
        precio_optimo = tarifario.precio_optimo if tarifario else Decimal('0')
        precio_estandar = tarifario.precio_estandar if tarifario else Decimal('0')
        fila.update({
            'bunches_optimos': fila['optimos'] // 25,
            'sueltos_optimos': fila['optimos'] % 25,
            'bunches_estandar': fila['estandar'] // 25,
            'sueltos_estandar': fila['estandar'] % 25,
            'precio_optimo': precio_optimo,
            'precio_estandar': precio_estandar,
            'valor_optimo': fila['optimos'] * precio_optimo,
            'valor_estandar': fila['estandar'] * precio_estandar,
        })
        fila['valor_total'] = fila['valor_optimo'] + fila['valor_estandar']
        filas_reporte.append(fila)
        for campo in ('mallas', 'tallos_recibidos', 'optimos', 'estandar', 'nacionales', 'sobrantes', 'valor_total'):
            totales[campo] += fila[campo]
    return render(request, 'liquidaciones/verLiquidacion.html', {
        'liquidacion': liquidacion,
        'detalles': liquidacion.detalleliquidacion_set.select_related('variedad', 'tarifario'),
        'filas_reporte': filas_reporte,
        'totales_reporte': dict(totales),
    })


def editarLiquidacion(request, codigo):
    return render(request, 'liquidaciones/editarLiquidacion.html', {
        'liquidacionEditar': get_object_or_404(Liquidacion, pk=codigo)
    })


@require_POST
def procesarEdicionLiquidacion(request):
    liquidacion = get_object_or_404(Liquidacion, pk=request.POST['codigo_liquidacion'])
    if liquidacion.estado == 'PAGADA':
        messages.error(request, 'Una liquidación pagada forma parte del historial y ya no puede modificarse.')
        return redirect('inicioLiquidacion')
    liquidacion.observacion = request.POST.get('observacion', '').strip()
    nuevo_documento = request.FILES.get('documento_proveedor')
    if nuevo_documento:
        try:
            nuevo_documento = validate_and_secure_document(nuevo_documento)
        except ValidationError as error:
            messages.error(request, ' '.join(error.messages))
            return redirect('editarLiquidacion', codigo=liquidacion.pk)
        liquidacion.documento_proveedor = nuevo_documento
        if liquidacion.estado != 'PAGADA':
            liquidacion.estado = 'PEND_PAGO'
    liquidacion.save()
    messages.success(request, 'Documento y observación actualizados exitosamente.')
    return redirect('inicioLiquidacion')


@require_POST
def marcarLiquidacionPagada(request, codigo):
    liquidacion = get_object_or_404(Liquidacion, pk=codigo)
    if liquidacion.estado == 'PAGADA':
        messages.info(request, 'La liquidación ya se encuentra pagada.')
    elif liquidacion.estado != 'PEND_PAGO' or not liquidacion.documento_proveedor:
        messages.error(request, 'Primero debe subir el documento enviado por el proveedor.')
    else:
        liquidacion.estado = 'PAGADA'
        liquidacion.save(update_fields=['estado', 'fecha_modificacion'])
        messages.success(request, 'Liquidación marcada como pagada exitosamente.')
    return redirect('inicioLiquidacion')
