from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.db.models import Exists, OuterRef, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from Aplicaciones.administracion.models import Finca, Personal, Proveedor, Variedad
from Aplicaciones.postcosecha.models import (
    Clasificacion,
    DetalleClasificacion,
    DetalleRecepcion,
    Recepcion,
    Tarifario,
)


def _generar_codigo(modelo, campo, prefijo, longitud=6):
    ultimo = modelo.objects.order_by(f'-{campo}').values_list(campo, flat=True).first()
    numero = int(ultimo[len(prefijo):]) + 1 if ultimo else 1
    return f'{prefijo}{numero:0{longitud}d}'


def _actualizar_estado_detalle(detalle):
    procesadas = detalle.detalleclasificacion_set.aggregate(total=Sum('cantidad_mallas_procesadas'))['total'] or 0
    if procesadas == 0:
        detalle.estado = 'PENDIENTE'
    elif procesadas < detalle.cantidad_mallas:
        detalle.estado = 'EN_CLASIFICACION'
    else:
        detalle.estado = 'CLASIFICADA'
    detalle.save()


def _horario_recepcion_valido(momento):
    """Valida el horario usando la zona horaria oficial configurada en Django."""
    dia_semana = momento.weekday()  # lunes=0, domingo=6
    hora_actual = momento.time()
    if 0 <= dia_semana <= 4:
        return time(8, 0) <= hora_actual <= time(15, 0)
    if dia_semana == 5:
        return time(8, 0) <= hora_actual <= time(12, 0)
    return False


def _fecha_clasificacion_valida(fecha, hoy, fecha_recepcion):
    """Permite hoy y los dos días siguientes, sin superar el plazo del lote."""
    return (
        hoy <= fecha <= hoy + timedelta(days=2)
        and fecha_recepcion <= fecha <= fecha_recepcion + timedelta(days=2)
    )


# Recepciones
def inicioRecepcion(request):
    recepciones = Recepcion.objects.select_related('proveedor', 'finca').prefetch_related(
        'detallerecepcion_set__variedad'
    ).order_by('-fecha_recepcion')
    return render(request, 'recepciones/inicioRecepcion.html', {'recepciones': recepciones})


def nuevaRecepcion(request):
    return render(request, 'recepciones/nuevaRecepcion.html', {
        'proveedores': Proveedor.objects.filter(estado=True).order_by('apellidos', 'nombres'),
        'fincas': Finca.objects.filter(estado=True).order_by('nombre'),
        'personal_postcosecha': Personal.objects.filter(
            estado=True, area__icontains='postcosecha'
        ).order_by('apellidos', 'nombres'),
        'variedades': Variedad.objects.filter(estado=True).order_by('nombre'),
    })


@require_POST
@transaction.atomic
def guardarRecepcion(request):
    if request.method != 'POST':
        return redirect('nuevaRecepcion')
    momento_recepcion = timezone.localtime(timezone.now())
    if not _horario_recepcion_valido(momento_recepcion):
        messages.error(
            request,
            'Recepción fuera del horario permitido: lunes a viernes de 08:00 a 15:00 '
            'y sábados de 08:00 a 12:00. Los domingos no se registran recepciones.',
        )
        return redirect('nuevaRecepcion')
    proveedor_codigo = request.POST.get('proveedor')
    finca_codigo = request.POST.get('finca')
    empleado_codigo = request.POST.get('empleado_receptor')
    if bool(proveedor_codigo) == bool(finca_codigo):
        messages.error(request, 'Seleccione únicamente un proveedor o una finca como origen')
        return redirect('/recepciones/nueva')
    empleado = get_object_or_404(
        Personal,
        pk=empleado_codigo,
        estado=True,
        area__icontains='postcosecha',
    )

    variedades = request.POST.getlist('variedad')
    cantidades = request.POST.getlist('cantidad_mallas')
    tallos_por_malla = request.POST.getlist('tallos_por_malla')
    if not variedades or not (len(variedades) == len(cantidades) == len(tallos_por_malla)):
        messages.error(request, 'La recepción debe contener al menos una variedad válida')
        return redirect('nuevaRecepcion')

    try:
        cantidades = [int(cantidad) for cantidad in cantidades]
        tallos_por_malla = [int(tallos) for tallos in tallos_por_malla]
        if any(valor < 1 for valor in cantidades + tallos_por_malla):
            raise ValueError
    except (TypeError, ValueError):
        messages.error(request, 'Las mallas y los tallos por malla deben ser mayores que cero')
        return redirect('nuevaRecepcion')

    ultimo_numero = Recepcion.objects.order_by('-numero_recepcion').values_list('numero_recepcion', flat=True).first()
    recepcion = Recepcion.objects.create(
        codigo_recepcion=_generar_codigo(Recepcion, 'codigo_recepcion', 'REC'),
        numero_recepcion=(ultimo_numero or 0) + 1,
        proveedor=get_object_or_404(Proveedor, pk=proveedor_codigo) if proveedor_codigo else None,
        finca=get_object_or_404(Finca, pk=finca_codigo) if finca_codigo else None,
        empleado_receptor=empleado,
        fecha_recepcion=momento_recepcion,
        observacion=request.POST.get('observacion', '').strip(),
    )
    for variedad_codigo, cantidad, tallos in zip(variedades, cantidades, tallos_por_malla):
        DetalleRecepcion.objects.create(
            recepcion=recepcion,
            variedad=get_object_or_404(Variedad, pk=variedad_codigo),
            cantidad_mallas=cantidad,
            tallos_por_malla=tallos,
        )
    messages.success(request, 'Recepción guardada exitosamente')
    return redirect('ticketRecepcion', codigo=recepcion.pk)


def ticketRecepcion(request, codigo):
    recepcion = get_object_or_404(
        Recepcion.objects.select_related('proveedor', 'finca').prefetch_related('detallerecepcion_set__variedad'),
        pk=codigo,
    )
    return render(request, 'recepciones/ticketRecepcion.html', {'recepcion': recepcion})


def detalleRecepcion(request, codigo):
    recepcion = get_object_or_404(
        Recepcion.objects.select_related('proveedor', 'finca').prefetch_related('detallerecepcion_set__variedad'),
        pk=codigo,
    )
    return render(request, 'recepciones/detalleRecepcion.html', {'recepcion': recepcion})


def editarRecepcion(request, codigo):
    return render(request, 'recepciones/editarRecepcion.html', {
        'recepcionEditar': get_object_or_404(Recepcion, pk=codigo),
        'detalles': DetalleRecepcion.objects.filter(recepcion_id=codigo).select_related('variedad'),
        'proveedores': Proveedor.objects.filter(estado=True).order_by('apellidos', 'nombres'),
        'fincas': Finca.objects.filter(estado=True).order_by('nombre'),
        'variedades': Variedad.objects.filter(estado=True).order_by('nombre'),
    })


@require_POST
@transaction.atomic
def procesarEdicionRecepcion(request):
    recepcion = get_object_or_404(Recepcion, pk=request.POST['codigo_recepcion'])
    proveedor_codigo = request.POST.get('proveedor')
    finca_codigo = request.POST.get('finca')
    if bool(proveedor_codigo) == bool(finca_codigo):
        messages.error(request, 'Seleccione únicamente un proveedor o una finca como origen')
        return redirect(f'/recepciones/editar/{recepcion.pk}')
    recepcion.proveedor = get_object_or_404(Proveedor, pk=proveedor_codigo) if proveedor_codigo else None
    recepcion.finca = get_object_or_404(Finca, pk=finca_codigo) if finca_codigo else None
    recepcion.observacion = request.POST.get('observacion', '').strip()
    recepcion.save()
    messages.success(request, 'Recepción actualizada exitosamente')
    return redirect('/recepciones')


@require_POST
def guardarDetalleRecepcion(request):
    detalle = DetalleRecepcion.objects.create(
        recepcion=get_object_or_404(Recepcion, pk=request.POST['codigo_recepcion']),
        variedad=get_object_or_404(Variedad, pk=request.POST['variedad']),
        cantidad_mallas=int(request.POST['cantidad_mallas']),
        tallos_por_malla=int(request.POST['tallos_por_malla']),
    )
    messages.success(request, 'Detalle agregado exitosamente')
    return redirect(f'/recepciones/editar/{detalle.recepcion_id}')


@require_POST
def procesarEdicionDetalleRecepcion(request):
    detalle = get_object_or_404(DetalleRecepcion, pk=request.POST['id'])
    detalle.variedad = get_object_or_404(Variedad, pk=request.POST['variedad'])
    detalle.cantidad_mallas = int(request.POST['cantidad_mallas'])
    detalle.tallos_por_malla = int(request.POST['tallos_por_malla'])
    detalle.save()
    _actualizar_estado_detalle(detalle)
    messages.success(request, 'Detalle actualizado exitosamente')
    return redirect(f'/recepciones/editar/{detalle.recepcion_id}')


@require_POST
def eliminarDetalleRecepcion(request, id):
    detalle = get_object_or_404(DetalleRecepcion, pk=id)
    recepcion_id = detalle.recepcion_id
    if detalle.detalleclasificacion_set.exists():
        messages.error(request, 'No se puede eliminar un detalle que ya fue clasificado')
    else:
        detalle.delete()
        messages.success(request, 'Detalle eliminado exitosamente')
    return redirect(f'/recepciones/editar/{recepcion_id}')


# Clasificaciones
def inicioClasificacion(request):
    clasificaciones = Clasificacion.objects.select_related(
        'recepcion__proveedor', 'recepcion__finca'
    ).prefetch_related(
        'recepcion__detallerecepcion_set__variedad',
        'detalleclasificacion_set__detalle_recepcion__variedad',
    ).order_by('-fecha_clasificacion')
    return render(request, 'clasificaciones/inicioClasificacion.html', {'clasificaciones': clasificaciones})


def reporteDiarioClasificacion(request):
    fecha = request.GET.get('fecha') or timezone.localdate().isoformat()
    try:
        fecha_consulta = datetime.strptime(fecha, '%Y-%m-%d').date()
    except ValueError:
        fecha_consulta = timezone.localdate()

    resultados = DetalleClasificacion.objects.filter(
        clasificacion__fecha_clasificacion=fecha_consulta,
        clasificacion__recepcion__isnull=False,
    ).values(
        'clasificacion_id',
        'clasificacion__recepcion__proveedor_id',
        'clasificacion__recepcion__finca_id',
        'detalle_recepcion__variedad_id',
        'largo',
    ).annotate(total_tallos=Sum('tallos_exportables'))

    resumen = {
        'bunches_optimos': 0,
        'bunches_estandar': 0,
        'bunches_proveedor': 0,
        'bunches_finca': 0,
        'tallos_sueltos': 0,
    }
    clasificaciones = set()
    for resultado in resultados:
        bunches, sueltos = divmod(resultado['total_tallos'] or 0, 25)
        clasificaciones.add(resultado['clasificacion_id'])
        resumen['tallos_sueltos'] += sueltos
        if resultado['largo'] == 'OPTIMO':
            resumen['bunches_optimos'] += bunches
        else:
            resumen['bunches_estandar'] += bunches
        if resultado['clasificacion__recepcion__proveedor_id']:
            resumen['bunches_proveedor'] += bunches
        elif resultado['clasificacion__recepcion__finca_id']:
            resumen['bunches_finca'] += bunches

    resumen['total_bunches'] = resumen['bunches_optimos'] + resumen['bunches_estandar']
    total = resumen['total_bunches']
    resumen['porcentaje_proveedor'] = round(resumen['bunches_proveedor'] * 100 / total, 1) if total else 0
    resumen['porcentaje_finca'] = round(resumen['bunches_finca'] * 100 / total, 1) if total else 0
    resumen['clasificaciones'] = len(clasificaciones)

    return render(request, 'clasificaciones/reporteDiarioClasificacion.html', {
        'fecha_consulta': fecha_consulta,
        'resumen': resumen,
    })


def nuevaClasificacion(request):
    hoy = timezone.localdate()
    fecha_maxima = hoy + timedelta(days=2)
    detalles = DetalleRecepcion.objects.filter(
        recepcion__clasificacion__isnull=True
    ).exclude(estado='CLASIFICADA').select_related(
        'recepcion', 'recepcion__proveedor', 'recepcion__finca', 'variedad'
    )
    recepciones_queryset = Recepcion.objects.filter(
        detallerecepcion__in=detalles
    ).select_related('proveedor', 'finca').prefetch_related(
        'detallerecepcion_set__variedad'
    ).distinct().order_by('-fecha_recepcion')
    recepciones_pendientes = []
    for recepcion in recepciones_queryset:
        fecha_recepcion = timezone.localtime(recepcion.fecha_recepcion).date()
        recepcion.fecha_limite_clasificacion = fecha_recepcion + timedelta(days=2)
        if recepcion.fecha_limite_clasificacion >= hoy:
            recepciones_pendientes.append(recepcion)
    return render(request, 'clasificaciones/nuevaClasificacion.html', {
        'fecha_minima': hoy,
        'fecha_maxima': fecha_maxima,
        'detalles_recepcion': detalles,
        'recepciones_pendientes': recepciones_pendientes,
        'variedades_pendientes': Variedad.objects.filter(
            detallerecepcion__in=detalles
        ).distinct().order_by('nombre'),
    })


@require_POST
@transaction.atomic
def guardarClasificacion(request):
    detalles_ids = request.POST.getlist('detalle_recepcion')
    mallas = request.POST.getlist('cantidad_mallas_procesadas')
    exportables_optimos = request.POST.getlist('tallos_exportables_optimos')
    exportables_estandar = request.POST.getlist('tallos_exportables_estandar')
    nacionales = request.POST.getlist('tallos_nacionales')
    sobrantes = request.POST.getlist('tallos_sobrantes')
    if not detalles_ids:
        messages.error(request, 'La clasificación debe contener al menos un detalle')
        return redirect('/clasificaciones/nueva')

    detalles_seleccionados = list(DetalleRecepcion.objects.filter(
        pk__in=detalles_ids
    ).select_related('recepcion', 'variedad'))
    if len(detalles_seleccionados) != len(set(detalles_ids)):
        messages.error(request, 'El lote contiene materiales inválidos o repetidos')
        return redirect('nuevaClasificacion')
    recepcion_ids = {detalle.recepcion_id for detalle in detalles_seleccionados}
    if len(recepcion_ids) != 1:
        messages.error(request, 'Cada clasificación debe pertenecer a una sola recepción y proveedor')
        return redirect('nuevaClasificacion')
    recepcion = detalles_seleccionados[0].recepcion
    try:
        fecha_clasificacion = datetime.strptime(
            request.POST.get('fecha_clasificacion', ''), '%Y-%m-%d'
        ).date()
    except ValueError:
        messages.error(request, 'Ingrese una fecha de clasificación válida')
        return redirect('nuevaClasificacion')
    hoy = timezone.localdate()
    fecha_recepcion = timezone.localtime(recepcion.fecha_recepcion).date()
    if not _fecha_clasificacion_valida(fecha_clasificacion, hoy, fecha_recepcion):
        messages.error(
            request,
            'La clasificación solo puede registrarse desde hoy hasta los dos días siguientes '
            'y siempre dentro de los tres días contados desde la recepción.',
        )
        return redirect('nuevaClasificacion')
    if Clasificacion.objects.filter(recepcion=recepcion).exists():
        messages.error(request, 'Esta recepción ya tiene un número de clasificación')
        return redirect('nuevaClasificacion')
    detalles_lote = list(DetalleRecepcion.objects.filter(recepcion=recepcion))
    if {detalle.pk for detalle in detalles_seleccionados} != {detalle.pk for detalle in detalles_lote}:
        messages.error(request, 'Debe clasificar todas las variedades del lote en el mismo momento')
        return redirect('nuevaClasificacion')
    cantidad_filas = len(detalles_ids)
    listas_numericas = (
        mallas, exportables_optimos, exportables_estandar, nacionales, sobrantes,
    )
    if any(len(lista) != cantidad_filas for lista in listas_numericas):
        messages.error(request, 'Complete todos los valores de la clasificación antes de guardarla')
        return redirect('nuevaClasificacion')
    try:
        filas_clasificadas = [
            {
                'detalle': next(detalle for detalle in detalles_seleccionados if detalle.pk == int(detalles_ids[indice])),
                'mallas': int(mallas[indice]),
                'optimos': int(exportables_optimos[indice] or 0),
                'estandar': int(exportables_estandar[indice] or 0),
                'nacionales': int(nacionales[indice] or 0),
                'sobrantes': int(sobrantes[indice] or 0),
            }
            for indice in range(cantidad_filas)
        ]
    except (TypeError, ValueError, StopIteration):
        messages.error(request, 'Las cantidades de la clasificación deben ser números enteros válidos')
        return redirect('nuevaClasificacion')
    if any(
        fila['mallas'] < 1 or any(fila[campo] < 0 for campo in ('optimos', 'estandar', 'nacionales', 'sobrantes'))
        for fila in filas_clasificadas
    ):
        messages.error(request, 'Las cantidades de tallos no pueden ser negativas')
        return redirect('nuevaClasificacion')
    for fila in filas_clasificadas:
        tallos_clasificados = fila['optimos'] + fila['estandar'] + fila['nacionales']
        if tallos_clasificados == 0 and fila['sobrantes'] == 0:
            messages.error(
                request,
                f"No puede finalizar {fila['detalle'].variedad.nombre} con todas las cantidades en cero. "
                'Registre el conteo real antes de guardar.',
            )
            return redirect('nuevaClasificacion')
        if tallos_clasificados > fila['detalle'].total_tallos:
            messages.error(
                request,
                f"La suma de óptimos, estándar y nacionales de {fila['detalle'].variedad.nombre} "
                f"no puede superar {fila['detalle'].total_tallos} tallos. "
                'Registre los tallos adicionales en Sobrantes.',
            )
            return redirect('nuevaClasificacion')
    cantidades_por_id = {
        fila['detalle'].pk: fila['mallas'] for fila in filas_clasificadas
    }
    if any(cantidades_por_id.get(detalle.pk) != detalle.cantidad_mallas for detalle in detalles_lote):
        messages.error(request, 'Debe procesar todas las mallas recibidas antes de guardar la clasificación')
        return redirect('nuevaClasificacion')

    clasificacion = Clasificacion.objects.create(
        codigo_clasificacion=_generar_codigo(Clasificacion, 'codigo_clasificacion', 'CLA'),
        recepcion=recepcion,
        fecha_clasificacion=fecha_clasificacion,
        observacion=request.POST.get('observacion', '').strip(),
    )
    observaciones_detalle = request.POST.getlist('observacion_detalle')
    for indice, fila in enumerate(filas_clasificadas):
        detalle = fila['detalle']
        ya_procesadas = detalle.detalleclasificacion_set.aggregate(total=Sum('cantidad_mallas_procesadas'))['total'] or 0
        cantidad_mallas = fila['mallas']
        if ya_procesadas + cantidad_mallas > detalle.cantidad_mallas:
            transaction.set_rollback(True)
            messages.error(request, f'Las mallas procesadas superan las recibidas para {detalle.variedad.nombre}')
            return redirect('/clasificaciones/nueva')
        DetalleClasificacion.objects.create(
            clasificacion=clasificacion, detalle_recepcion=detalle,
            cantidad_mallas_procesadas=cantidad_mallas, largo='OPTIMO',
            tallos_exportables=fila['optimos'],
            tallos_nacionales=fila['nacionales'],
            tallos_sobrantes=fila['sobrantes'],
            observacion=observaciones_detalle[indice] if indice < len(observaciones_detalle) else '',
        )
        DetalleClasificacion.objects.create(
            clasificacion=clasificacion, detalle_recepcion=detalle,
            cantidad_mallas_procesadas=0, largo='ESTANDAR',
            tallos_exportables=fila['estandar'],
        )
        _actualizar_estado_detalle(detalle)
    messages.success(request, 'Clasificación guardada exitosamente')
    return redirect('reporteClasificacion', codigo=clasificacion.pk)


def reporteClasificacion(request, codigo):
    clasificacion = get_object_or_404(Clasificacion, pk=codigo)
    recepcion_ids = clasificacion.detalleclasificacion_set.values_list(
        'detalle_recepcion__recepcion_id', flat=True
    ).distinct()
    recepciones = Recepcion.objects.filter(pk__in=recepcion_ids).select_related(
        'proveedor', 'finca', 'empleado_receptor'
    ).prefetch_related(
        'detallerecepcion_set__variedad',
        'detallerecepcion_set__detalleclasificacion_set',
    )
    reportes = []
    for recepcion in recepciones:
        filas = defaultdict(lambda: {
            'mallas_recibidas': 0, 'tallos_recibidos': 0,
            'exportables_optimos': 0, 'exportables_estandar': 0,
            'nacionales': 0, 'sobrantes_clasificacion': 0,
            'tallos_contabilizados': 0, 'faltantes': 0,
        })
        completa = True
        for detalle in recepcion.detallerecepcion_set.all():
            fila = filas[detalle.variedad.nombre]
            fila['mallas_recibidas'] += detalle.cantidad_mallas
            fila['tallos_recibidos'] += detalle.total_tallos
            completa = completa and detalle.estado == 'CLASIFICADA'
            for resultado in detalle.detalleclasificacion_set.all():
                clave = 'exportables_optimos' if resultado.largo == 'OPTIMO' else 'exportables_estandar'
                fila[clave] += resultado.tallos_exportables
                fila['nacionales'] += resultado.tallos_nacionales
                fila['sobrantes_clasificacion'] += resultado.tallos_sobrantes

        filas_reporte = []
        for variedad, datos in sorted(filas.items()):
            tallos_clasificados = (
                datos['exportables_optimos'] + datos['exportables_estandar'] + datos['nacionales']
            )
            datos['faltantes'] = max(datos['tallos_recibidos'] - tallos_clasificados, 0)
            datos['tallos_contabilizados'] = tallos_clasificados + datos['sobrantes_clasificacion']
            datos.update({
                'variedad': variedad,
                'bunches_optimos': datos['exportables_optimos'] // 25,
                'tallos_bunches_optimos': (datos['exportables_optimos'] // 25) * 25,
                'sueltos_optimos': datos['exportables_optimos'] % 25,
                'bunches_estandar': datos['exportables_estandar'] // 25,
                'tallos_bunches_estandar': (datos['exportables_estandar'] // 25) * 25,
                'sueltos_estandar': datos['exportables_estandar'] % 25,
                'total_exportables': datos['exportables_optimos'] + datos['exportables_estandar'],
            })
            filas_reporte.append(datos)
        reportes.append({'recepcion': recepcion, 'completa': completa, 'filas': filas_reporte})
    return render(request, 'clasificaciones/reporteClasificacion.html', {
        'clasificacion': clasificacion, 'reportes': reportes,
    })


def editarClasificacion(request, codigo):
    clasificacion = get_object_or_404(Clasificacion, pk=codigo)
    resultados = clasificacion.detalleclasificacion_set.select_related(
        'detalle_recepcion__variedad'
    ).order_by('detalle_recepcion_id', 'largo')
    grupos = {}
    for resultado in resultados:
        detalle = resultado.detalle_recepcion
        grupo = grupos.setdefault(detalle.variedad_id, {
            'variedad': detalle.variedad.nombre,
            'mallas': 0,
            'tallos_recibidos': 0,
            'nacionales': 0,
            'sobrantes': 0,
            'detalles_contados': set(),
            'calidades': {
                'ESTANDAR': {'nombre': 'Estándar', 'exportables': 0, 'bunches': 0},
                'OPTIMO': {'nombre': 'Óptimo', 'exportables': 0, 'bunches': 0},
            },
        })
        if detalle.pk not in grupo['detalles_contados']:
            grupo['mallas'] += detalle.cantidad_mallas
            grupo['tallos_recibidos'] += detalle.total_tallos
            grupo['detalles_contados'].add(detalle.pk)
        grupo['nacionales'] += resultado.tallos_nacionales
        grupo['sobrantes'] += resultado.tallos_sobrantes
        calidad = grupo['calidades'][resultado.largo]
        calidad['nombre'] = resultado.get_largo_display()
        calidad['exportables'] += resultado.tallos_exportables

    detalles_agrupados = []
    for grupo in grupos.values():
        for calidad in grupo['calidades'].values():
            calidad['bunches'] = calidad['exportables'] // 25
        tallos_clasificados = (
            grupo['calidades']['OPTIMO']['exportables']
            + grupo['calidades']['ESTANDAR']['exportables']
            + grupo['nacionales']
        )
        grupo['faltantes'] = max(grupo['tallos_recibidos'] - tallos_clasificados, 0)
        grupo['tallos_contabilizados'] = tallos_clasificados + grupo['sobrantes']
        grupo['calidades'] = [
            grupo['calidades']['ESTANDAR'],
            grupo['calidades']['OPTIMO'],
        ]
        detalles_agrupados.append(grupo)
    return render(request, 'clasificaciones/editarClasificacion.html', {
        'clasificacionEditar': clasificacion,
        'detalles_agrupados': detalles_agrupados,
    })


@require_POST
def procesarEdicionClasificacion(request):
    clasificacion = get_object_or_404(Clasificacion, pk=request.POST['codigo_clasificacion'])
    clasificacion.observacion = request.POST.get('observacion', '').strip()
    clasificacion.save()
    messages.success(request, 'Clasificación actualizada exitosamente')
    return redirect('/clasificaciones')


# Tarifarios
def inicioTarifario(request):
    from Aplicaciones.liquidaciones.models import DetalleLiquidacion

    tarifarios = Tarifario.objects.select_related('variedad').annotate(
        utilizado=Exists(
            DetalleLiquidacion.objects.filter(tarifario_id=OuterRef('pk'))
        )
    ).order_by('-fecha_inicio', 'variedad__nombre')
    for tarifario in tarifarios:
        tarifario.puede_editar = tarifario.estado and not tarifario.utilizado
    return render(request, 'tarifarios/inicioTarifario.html', {
        'tarifarios': tarifarios,
    })


def nuevoTarifario(request):
    variedades = list(Variedad.objects.filter(estado=True).order_by('nombre'))
    activos = {
        tarifario.variedad_id: tarifario
        for tarifario in Tarifario.objects.filter(estado=True)
    }
    for variedad in variedades:
        variedad.tarifario_actual = activos.get(variedad.pk)
    return render(request, 'tarifarios/nuevoTarifario.html', {
        'variedades': variedades,
    })


@require_POST
@transaction.atomic
def guardarTarifario(request):
    variedad = get_object_or_404(Variedad, pk=request.POST.get('variedad'), estado=True)
    try:
        fecha_inicio = datetime.strptime(request.POST.get('fecha_inicio', ''), '%Y-%m-%d').date()
        precio_optimo = Decimal((request.POST.get('precio_optimo') or '').replace(',', '.'))
        precio_estandar = Decimal((request.POST.get('precio_estandar') or '').replace(',', '.'))
        if precio_optimo <= 0 or precio_estandar <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        messages.error(request, 'Ingrese una fecha válida y precios mayores que cero')
        return redirect('nuevoTarifario')

    tarifario_activo = Tarifario.objects.filter(variedad=variedad, estado=True).first()
    if tarifario_activo and fecha_inicio <= tarifario_activo.fecha_inicio:
        messages.error(
            request,
            f'La nueva vigencia debe iniciar después del {tarifario_activo.fecha_inicio:%d/%m/%Y}. '
            'Si el tarifario actual está equivocado y no se ha utilizado, use Corregir.',
        )
        return redirect('nuevoTarifario')
    ultimo = Tarifario.objects.filter(variedad=variedad).order_by('-fecha_inicio').first()
    if not tarifario_activo and ultimo and ultimo.fecha_fin and fecha_inicio <= ultimo.fecha_fin:
        messages.error(request, 'La fecha se superpone con una vigencia anterior')
        return redirect('nuevoTarifario')

    if tarifario_activo:
        tarifario_activo.estado = False
        tarifario_activo.fecha_fin = fecha_inicio - timedelta(days=1)
        tarifario_activo.save(update_fields=['estado', 'fecha_fin', 'fecha_modificacion'])
    Tarifario.objects.create(
        codigo_tarifario=_generar_codigo(Tarifario, 'codigo_tarifario', 'TAR'),
        variedad=variedad,
        precio_optimo=precio_optimo,
        precio_estandar=precio_estandar,
        fecha_inicio=fecha_inicio,
    )
    messages.success(request, 'Tarifario guardado exitosamente')
    return redirect('/tarifarios')


def editarTarifario(request, codigo):
    from Aplicaciones.liquidaciones.models import DetalleLiquidacion

    tarifario = get_object_or_404(Tarifario.objects.select_related('variedad'), pk=codigo)
    if not tarifario.estado or DetalleLiquidacion.objects.filter(tarifario=tarifario).exists():
        messages.error(request, 'Este tarifario ya forma parte del historial y no puede modificarse')
        return redirect('inicioTarifario')
    return render(request, 'tarifarios/editarTarifario.html', {'tarifario': tarifario})


@require_POST
@transaction.atomic
def procesarEdicionTarifario(request):
    from Aplicaciones.liquidaciones.models import DetalleLiquidacion

    tarifario = get_object_or_404(Tarifario, pk=request.POST.get('codigo_tarifario'))
    if not tarifario.estado or DetalleLiquidacion.objects.filter(tarifario=tarifario).exists():
        messages.error(request, 'El precio ya fue utilizado o pertenece al historial; no puede modificarse')
        return redirect('inicioTarifario')
    try:
        fecha_inicio = datetime.strptime(request.POST.get('fecha_inicio', ''), '%Y-%m-%d').date()
        precio_optimo = Decimal((request.POST.get('precio_optimo') or '').replace(',', '.'))
        precio_estandar = Decimal((request.POST.get('precio_estandar') or '').replace(',', '.'))
        if precio_optimo <= 0 or precio_estandar <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        messages.error(request, 'Ingrese una fecha válida y precios mayores que cero')
        return redirect('editarTarifario', codigo=tarifario.pk)

    vigencia_anterior = Tarifario.objects.filter(
        variedad=tarifario.variedad,
    ).exclude(pk=tarifario.pk).order_by('-fecha_inicio').first()
    if vigencia_anterior and (
        fecha_inicio <= vigencia_anterior.fecha_inicio
        or (vigencia_anterior.fecha_fin and fecha_inicio <= vigencia_anterior.fecha_fin)
    ):
        messages.error(request, 'La fecha corregida se superpone con una vigencia anterior')
        return redirect('editarTarifario', codigo=tarifario.pk)

    tarifario.fecha_inicio = fecha_inicio
    tarifario.precio_optimo = precio_optimo
    tarifario.precio_estandar = precio_estandar
    tarifario.save()
    messages.success(request, 'Tarifario corregido. Se conservó el mismo código y vigencia activa')
    return redirect('inicioTarifario')


@require_POST
def cerrarTarifario(request, codigo):
    tarifario = get_object_or_404(Tarifario, pk=codigo)
    if not tarifario.estado:
        messages.error(request, 'El tarifario ya se encuentra cerrado')
        return redirect('inicioTarifario')
    try:
        fecha_fin = datetime.strptime(request.POST.get('fecha_fin', ''), '%Y-%m-%d').date()
        if fecha_fin < tarifario.fecha_inicio:
            raise ValueError
    except ValueError:
        messages.error(request, 'La fecha de cierre no puede ser anterior al inicio de vigencia')
        return redirect('inicioTarifario')
    tarifario.fecha_fin = fecha_fin
    tarifario.estado = False
    tarifario.save()
    messages.success(request, 'Vigencia del tarifario cerrada exitosamente')
    return redirect('/tarifarios')
