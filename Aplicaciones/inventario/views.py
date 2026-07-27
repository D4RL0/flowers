from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import F, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from Aplicaciones.administracion.models import Finca
from Aplicaciones.administracion.validators import telefono_ecuatoriano_valido
from Aplicaciones.inventario.models import (
    Categoria,
    DetalleEntrada,
    DetalleSalida,
    Entrada,
    Producto,
    ProveedorInsumo,
    Salida,
    UnidadMedida,
)


def _generar_codigo(modelo, campo, prefijo, longitud=4):
    ultimo = modelo.objects.order_by(f'-{campo}').values_list(campo, flat=True).first()
    numero = int(ultimo[len(prefijo):]) + 1 if ultimo else 1
    return f'{prefijo}{numero:0{longitud}d}'


# Proveedores de insumos
def inicioProveedorInsumo(request):
    return render(request, 'proveedores_insumos/inicioProveedorInsumo.html', {
        'proveedores_insumos': ProveedorInsumo.objects.all().order_by('nombre_empresa')
    })


def nuevoProveedorInsumo(request):
    return render(request, 'proveedores_insumos/nuevoProveedorInsumo.html')


@require_POST
def guardarProveedorInsumo(request):
    telefono = request.POST.get('telefono', '').strip()
    if not telefono_ecuatoriano_valido(telefono):
        messages.error(request, 'Ingrese un celular nacional 09 de 10 dígitos o un teléfono local de 7 dígitos')
        return redirect('nuevoProveedorInsumo')
    ProveedorInsumo.objects.create(
        codigo_proveedor_insumo=_generar_codigo(ProveedorInsumo, 'codigo_proveedor_insumo', 'PINS'),
        nombre_contacto=request.POST['nombre_contacto'].strip(),
        nombre_empresa=request.POST['nombre_empresa'].strip(),
        telefono=telefono,
    )
    messages.success(request, 'Proveedor de insumos guardado exitosamente')
    return redirect('/proveedores-insumos')


def editarProveedorInsumo(request, codigo):
    return render(request, 'proveedores_insumos/editarProveedorInsumo.html', {
        'proveedorEditar': get_object_or_404(ProveedorInsumo, pk=codigo)
    })


@require_POST
def procesarEdicionProveedorInsumo(request):
    proveedor = get_object_or_404(ProveedorInsumo, pk=request.POST['codigo_proveedor_insumo'])
    telefono = request.POST.get('telefono', '').strip()
    if not telefono_ecuatoriano_valido(telefono):
        messages.error(request, 'Ingrese un celular nacional 09 de 10 dígitos o un teléfono local de 7 dígitos')
        return redirect('editarProveedorInsumo', codigo=proveedor.pk)
    proveedor.nombre_contacto = request.POST['nombre_contacto'].strip()
    proveedor.nombre_empresa = request.POST['nombre_empresa'].strip()
    proveedor.telefono = telefono
    proveedor.save()
    messages.success(request, 'Proveedor de insumos actualizado exitosamente')
    return redirect('/proveedores-insumos')


@require_POST
def cambiarEstadoProveedorInsumo(request, codigo):
    proveedor = get_object_or_404(ProveedorInsumo, pk=codigo)
    proveedor.estado = not proveedor.estado
    proveedor.save()
    messages.success(request, 'Estado actualizado exitosamente')
    return redirect('/proveedores-insumos')


# Categorías
def inicioCategoria(request):
    return render(request, 'categorias/inicioCategoria.html', {
        'categorias': Categoria.objects.prefetch_related(
            Prefetch('producto_set', queryset=Producto.objects.filter(estado=True), to_attr='productos_activos')
        ).order_by('nombre')
    })


def nuevaCategoria(request):
    return render(request, 'categorias/nuevaCategoria.html')


@require_POST
def guardarCategoria(request):
    Categoria.objects.create(
        codigo_categoria=_generar_codigo(Categoria, 'codigo_categoria', 'CAT'),
        nombre=request.POST['nombre'].strip(),
        descripcion=request.POST.get('descripcion', '').strip(),
    )
    messages.success(request, 'Categoría guardada exitosamente')
    return redirect('/categorias')


def editarCategoria(request, codigo):
    return render(request, 'categorias/editarCategoria.html', {
        'categoriaEditar': get_object_or_404(Categoria, pk=codigo)
    })


@require_POST
def procesarEdicionCategoria(request):
    categoria = get_object_or_404(Categoria, pk=request.POST['codigo_categoria'])
    categoria.nombre = request.POST['nombre'].strip()
    categoria.descripcion = request.POST.get('descripcion', '').strip()
    categoria.save()
    messages.success(request, 'Categoría actualizada exitosamente')
    return redirect('/categorias')


@require_POST
def cambiarEstadoCategoria(request, codigo):
    categoria = get_object_or_404(Categoria, pk=codigo)
    categoria.estado = not categoria.estado
    categoria.save()
    messages.success(request, 'Estado de la categoría actualizado exitosamente')
    return redirect('/categorias')


# Unidades de medida
def inicioUnidadMedida(request):
    return render(request, 'unidades_medida/inicioUnidadMedida.html', {
        'unidades': UnidadMedida.objects.all().order_by('nombre')
    })


def nuevaUnidadMedida(request):
    return render(request, 'unidades_medida/nuevaUnidadMedida.html')


@require_POST
def guardarUnidadMedida(request):
    nombre = request.POST.get('nombre', '').strip().upper()
    abreviatura = request.POST.get('abreviatura', '').strip().upper()
    if UnidadMedida.objects.filter(nombre__iexact=nombre).exists():
        messages.error(request, 'Ya existe una unidad de medida con ese nombre')
        return redirect('nuevaUnidadMedida')
    if UnidadMedida.objects.filter(abreviatura__iexact=abreviatura).exists():
        messages.error(request, 'Ya existe una unidad de medida con esa abreviatura')
        return redirect('nuevaUnidadMedida')
    UnidadMedida.objects.create(
        codigo_unidad_medida=_generar_codigo(UnidadMedida, 'codigo_unidad_medida', 'UM'),
        nombre=nombre,
        abreviatura=abreviatura,
    )
    messages.success(request, 'Unidad de medida guardada exitosamente')
    return redirect('/unidades-medida')


@require_POST
def guardarUnidadMedidaRapida(request):
    nombre = request.POST.get('nombre', '').strip().upper()
    abreviatura = request.POST.get('abreviatura', '').strip().upper()
    if not nombre or not abreviatura:
        return JsonResponse({'ok': False, 'error': 'Escriba el nombre y la abreviatura.'}, status=400)
    if UnidadMedida.objects.filter(nombre__iexact=nombre).exists():
        return JsonResponse({'ok': False, 'error': 'Ya existe una unidad con ese nombre.'}, status=400)
    if UnidadMedida.objects.filter(abreviatura__iexact=abreviatura).exists():
        return JsonResponse({'ok': False, 'error': 'Ya existe una unidad con esa abreviatura.'}, status=400)
    unidad = UnidadMedida.objects.create(
        codigo_unidad_medida=_generar_codigo(UnidadMedida, 'codigo_unidad_medida', 'UM'),
        nombre=nombre,
        abreviatura=abreviatura,
    )
    return JsonResponse({
        'ok': True,
        'codigo': unidad.codigo_unidad_medida,
        'texto': f'{unidad.nombre} ({unidad.abreviatura})',
    })


def editarUnidadMedida(request, codigo):
    return render(request, 'unidades_medida/editarUnidadMedida.html', {
        'unidadEditar': get_object_or_404(UnidadMedida, pk=codigo)
    })


@require_POST
def procesarEdicionUnidadMedida(request):
    unidad = get_object_or_404(UnidadMedida, pk=request.POST['codigo_unidad_medida'])
    nombre = request.POST.get('nombre', '').strip().upper()
    abreviatura = request.POST.get('abreviatura', '').strip().upper()
    if UnidadMedida.objects.exclude(pk=unidad.pk).filter(nombre__iexact=nombre).exists():
        messages.error(request, 'Ya existe una unidad de medida con ese nombre')
        return redirect('editarUnidadMedida', codigo=unidad.pk)
    if UnidadMedida.objects.exclude(pk=unidad.pk).filter(abreviatura__iexact=abreviatura).exists():
        messages.error(request, 'Ya existe una unidad de medida con esa abreviatura')
        return redirect('editarUnidadMedida', codigo=unidad.pk)
    unidad.nombre = nombre
    unidad.abreviatura = abreviatura
    unidad.save()
    messages.success(request, 'Unidad de medida actualizada exitosamente')
    return redirect('/unidades-medida')


@require_POST
def cambiarEstadoUnidadMedida(request, codigo):
    unidad = get_object_or_404(UnidadMedida, pk=codigo)
    unidad.estado = not unidad.estado
    unidad.save()
    messages.success(request, 'Estado de la unidad actualizado exitosamente')
    return redirect('/unidades-medida')


# Productos químicos
def inicioProducto(request):
    categoria_seleccionada = None
    productos_activos = Producto.objects.filter(estado=True).select_related(
        'unidad_medida'
    ).order_by('nombre')
    codigo_categoria = request.GET.get('categoria', '').strip()
    if codigo_categoria:
        categoria_seleccionada = get_object_or_404(Categoria, pk=codigo_categoria)
        productos_activos = productos_activos.filter(categoria=categoria_seleccionada)
    categorias = Categoria.objects.filter(estado=True).prefetch_related(
        Prefetch('producto_set', queryset=productos_activos, to_attr='productos_inventario')
    ).order_by('nombre')
    if categoria_seleccionada:
        categorias = categorias.filter(pk=categoria_seleccionada.pk)
    return render(request, 'productos/inicioProducto.html', {
        'categorias': categorias,
        'categoria_seleccionada': categoria_seleccionada,
    })


def nuevoProducto(request):
    categorias = Categoria.objects.filter(estado=True).order_by('nombre')
    if not categorias.exists():
        messages.warning(request, 'Primero debe crear una categoría activa para poder registrar productos')
        return redirect('nuevaCategoria')
    return render(request, 'productos/nuevoProducto.html', {
        'categorias': categorias,
        'unidades': UnidadMedida.objects.filter(estado=True).order_by('nombre'),
        'categoria_seleccionada': request.GET.get('categoria', '').strip(),
    })


@require_POST
def guardarProducto(request):
    Producto.objects.create(
        codigo_producto=_generar_codigo(Producto, 'codigo_producto', 'PROD'),
        categoria=get_object_or_404(Categoria, pk=request.POST['categoria']),
        unidad_medida=get_object_or_404(UnidadMedida, pk=request.POST['unidad_medida']),
        nombre=request.POST['nombre'].strip(),
        marca=request.POST.get('marca', '').strip(),
        stock_minimo=Decimal(request.POST['stock_minimo'].replace(',', '.')),
    )
    messages.success(request, 'Producto guardado exitosamente')
    return redirect('/productos')


def editarProducto(request, codigo):
    return render(request, 'productos/editarProducto.html', {
        'productoEditar': get_object_or_404(Producto, pk=codigo),
        'categorias': Categoria.objects.filter(estado=True).order_by('nombre'),
        'unidades': UnidadMedida.objects.filter(estado=True).order_by('nombre'),
    })


@require_POST
def procesarEdicionProducto(request):
    producto = get_object_or_404(Producto, pk=request.POST['codigo_producto'])
    producto.categoria = get_object_or_404(Categoria, pk=request.POST['categoria'])
    producto.unidad_medida = get_object_or_404(UnidadMedida, pk=request.POST['unidad_medida'])
    producto.nombre = request.POST['nombre'].strip()
    producto.marca = request.POST.get('marca', '').strip()
    producto.stock_minimo = Decimal(request.POST['stock_minimo'].replace(',', '.'))
    producto.save()
    messages.success(request, 'Producto actualizado exitosamente')
    return redirect('/productos')


@require_POST
def cambiarEstadoProducto(request, codigo):
    producto = get_object_or_404(Producto, pk=codigo)
    producto.estado = not producto.estado
    producto.save()
    messages.success(request, 'Estado del producto actualizado exitosamente')
    return redirect('/productos')


# Entradas
def inicioEntrada(request):
    entradas = Entrada.objects.select_related('proveedor_insumo').prefetch_related(
        'detalleentrada_set__producto'
    ).order_by('-fecha_entrada')
    return render(request, 'entradas/inicioEntrada.html', {'entradas': entradas})


def nuevaEntrada(request):
    return render(request, 'entradas/nuevaEntrada.html', {
        'proveedores_insumos': ProveedorInsumo.objects.filter(estado=True).order_by('nombre_empresa'),
        'productos': Producto.objects.filter(estado=True).select_related('unidad_medida').order_by('nombre'),
    })


@require_POST
@transaction.atomic
def guardarEntrada(request):
    productos_ids = request.POST.getlist('producto')
    presentaciones = request.POST.getlist('tipo_presentacion')
    contenidos = request.POST.getlist('contenido_presentacion')
    envases = request.POST.getlist('cantidad_envases')
    if not productos_ids:
        messages.error(request, 'La entrada debe contener al menos un producto')
        return redirect('/entradas/nueva')

    entrada = Entrada.objects.create(
        codigo_entrada=_generar_codigo(Entrada, 'codigo_entrada', 'ENT', 6),
        proveedor_insumo=get_object_or_404(ProveedorInsumo, pk=request.POST['proveedor_insumo']),
        fecha_entrada=request.POST['fecha_entrada'],
        numero_factura=request.POST.get('numero_factura', '').strip(),
        observacion=request.POST.get('observacion', '').strip(),
    )
    for indice, producto_id in enumerate(productos_ids):
        producto = Producto.objects.select_for_update().get(pk=producto_id)
        contenido = Decimal(contenidos[indice].replace(',', '.'))
        cantidad_envases = int(envases[indice])
        cantidad_ingresada = contenido * cantidad_envases
        DetalleEntrada.objects.create(
            entrada=entrada,
            producto=producto,
            tipo_presentacion=presentaciones[indice].strip(),
            contenido_presentacion=contenido,
            cantidad_envases=cantidad_envases,
            cantidad_ingresada=cantidad_ingresada,
        )
        Producto.objects.filter(pk=producto.pk).update(existencia_actual=F('existencia_actual') + cantidad_ingresada)
    messages.success(request, 'Entrada registrada y existencias actualizadas exitosamente')
    return redirect('/entradas')


def verEntrada(request, codigo):
    entrada = get_object_or_404(Entrada.objects.select_related('proveedor_insumo'), pk=codigo)
    return render(request, 'entradas/verEntrada.html', {
        'entrada': entrada,
        'detalles': entrada.detalleentrada_set.select_related('producto__unidad_medida'),
    })


# Salidas
def inicioSalida(request):
    salidas = Salida.objects.select_related('finca').prefetch_related(
        'detallesalida_set__producto'
    ).order_by('-fecha_salida')
    return render(request, 'salidas/inicioSalida.html', {'salidas': salidas})


def nuevaSalida(request):
    return render(request, 'salidas/nuevaSalida.html', {
        'fincas': Finca.objects.filter(estado=True).order_by('nombre'),
        'productos': Producto.objects.filter(estado=True).select_related('unidad_medida').order_by('nombre'),
    })


@require_POST
@transaction.atomic
def guardarSalida(request):
    productos_ids = request.POST.getlist('producto')
    cantidades = request.POST.getlist('cantidad_salida')
    if not productos_ids:
        messages.error(request, 'La salida debe contener al menos un producto')
        return redirect('/salidas/nueva')

    salida = Salida.objects.create(
        codigo_salida=_generar_codigo(Salida, 'codigo_salida', 'SAL', 6),
        finca=get_object_or_404(Finca, pk=request.POST['finca']),
        fecha_salida=request.POST['fecha_salida'],
        destino=request.POST.get('destino', '').strip(),
        motivo=request.POST['motivo'].strip(),
        observacion=request.POST.get('observacion', '').strip(),
    )
    for indice, producto_id in enumerate(productos_ids):
        producto = Producto.objects.select_for_update().get(pk=producto_id)
        cantidad = Decimal(cantidades[indice].replace(',', '.'))
        if cantidad > producto.existencia_actual:
            transaction.set_rollback(True)
            messages.error(request, f'Existencia insuficiente para {producto.nombre}')
            return redirect('/salidas/nueva')
        DetalleSalida.objects.create(salida=salida, producto=producto, cantidad_salida=cantidad)
        Producto.objects.filter(pk=producto.pk).update(existencia_actual=F('existencia_actual') - cantidad)
    messages.success(request, 'Salida registrada y existencias actualizadas exitosamente')
    return redirect('/salidas')


def verSalida(request, codigo):
    salida = get_object_or_404(Salida.objects.select_related('finca'), pk=codigo)
    return render(request, 'salidas/verSalida.html', {
        'salida': salida,
        'detalles': salida.detallesalida_set.select_related('producto__unidad_medida'),
    })


def historialMovimientos(request):
    return render(request, 'movimientos/historialMovimientos.html', {
        'entradas': DetalleEntrada.objects.select_related('entrada', 'producto__unidad_medida').order_by('-entrada__fecha_entrada'),
        'salidas': DetalleSalida.objects.select_related('salida', 'producto__unidad_medida').order_by('-salida__fecha_salida'),
        'total_entradas': Entrada.objects.count(),
        'total_salidas': Salida.objects.count(),
    })
