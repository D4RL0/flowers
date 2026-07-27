from datetime import date, datetime, time
from decimal import Decimal


SENSITIVE_FIELDS = {
    'csrfmiddlewaretoken', 'password', 'password_confirmacion', 'archivo',
    'documento_proveedor', 'token',
}

ACTION_LABELS = {
    'guardarUsuario': 'CREAR USUARIO',
    'procesarUsuario': 'EDITAR USUARIO',
    'guardarProveedor': 'CREAR PROVEEDOR',
    'procesarEdicionProveedor': 'EDITAR PROVEEDOR',
    'cambiarEstadoProveedor': 'CAMBIAR ESTADO DE PROVEEDOR',
    'guardarVariedad': 'CREAR VARIEDAD',
    'procesarEdicionVariedad': 'EDITAR VARIEDAD',
    'guardarFinca': 'CREAR FINCA',
    'procesarEdicionFinca': 'EDITAR FINCA',
    'guardarPersonal': 'CREAR PERSONAL',
    'procesarEdicionPersonal': 'EDITAR PERSONAL',
    'guardarPermisoPersonal': 'REGISTRAR PERMISO',
    'guardarVacacionPersonal': 'REGISTRAR VACACIONES',
    'guardarDocumentoPersonal': 'CARGAR DOCUMENTO DE PERSONAL',
    'guardarRecepcion': 'CREAR RECEPCIÓN',
    'procesarEdicionRecepcion': 'EDITAR RECEPCIÓN',
    'guardarClasificacion': 'CREAR CLASIFICACIÓN',
    'procesarEdicionClasificacion': 'EDITAR CLASIFICACIÓN',
    'guardarTarifario': 'CREAR TARIFARIO',
    'procesarEdicionTarifario': 'EDITAR TARIFARIO',
    'procesarEdicionLiquidacion': 'CARGAR DOCUMENTO DE LIQUIDACIÓN',
    'marcarLiquidacionPagada': 'MARCAR LIQUIDACIÓN PAGADA',
    'guardarEntrada': 'REGISTRAR ENTRADA DE INVENTARIO',
    'guardarSalida': 'REGISTRAR SALIDA DE INVENTARIO',
}

IDENTIFIER_FIELDS = (
    'codigo_liquidacion', 'codigo_clasificacion', 'codigo_recepcion',
    'codigo_personal', 'codigo_producto', 'codigo_categoria',
    'codigo_unidad_medida', 'codigo_proveedor_insumo', 'codigo_proveedor',
    'codigo_variedad', 'codigo_finca', 'id',
)


def safe_request_data(request):
    data = {}
    for key in request.POST:
        if key.lower() in SENSITIVE_FIELDS:
            data[key] = '[PROTEGIDO]'
            continue
        values = [str(value)[:500] for value in request.POST.getlist(key)]
        data[key] = values if len(values) > 1 else (values[0] if values else '')
    for key in request.FILES:
        archivo = request.FILES[key]
        data[key] = {'archivo': '[PROTEGIDO]', 'tamano_bytes': archivo.size}
    return data


def record_identifier(match, request):
    if match.kwargs:
        return str(next(iter(match.kwargs.values())))[:50]
    for field in IDENTIFIER_FIELDS:
        value = request.POST.get(field)
        if value:
            return str(value)[:50]
    return ''


def readable_action(url_name):
    if url_name in ACTION_LABELS:
        return ACTION_LABELS[url_name]
    words = []
    current = ''
    for character in url_name or 'OPERACION':
        if character.isupper() and current:
            words.append(current)
            current = character
        else:
            current += character
    words.append(current)
    return ' '.join(words).upper()


def entity_from_path(path):
    return (path.strip('/').split('/')[0] or 'sistema').replace('-', '_')[:100]


def _json_value(value):
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'pk'):
        return str(value.pk)
    return value


def model_snapshot(instance):
    if instance is None:
        return None
    excluded = {'password', 'archivo', 'documento_proveedor'}
    result = {}
    for field in instance._meta.concrete_fields:
        if field.name in excluded:
            result[field.name] = '[PROTEGIDO]' if getattr(instance, field.name, None) else ''
        else:
            result[field.name] = _json_value(getattr(instance, field.name))
    return result


def snapshot_for_action(url_name, identifier):
    if not identifier:
        return None
    from django.contrib.auth import get_user_model
    from Aplicaciones.administracion.models import Finca, Personal, Proveedor, Variedad
    from Aplicaciones.inventario.models import Categoria, Producto, ProveedorInsumo, UnidadMedida
    from Aplicaciones.liquidaciones.models import Liquidacion
    from Aplicaciones.postcosecha.models import Clasificacion, Recepcion, Tarifario

    registry = {
        'procesarUsuario': get_user_model(),
        'procesarEdicionProveedor': Proveedor,
        'cambiarEstadoProveedor': Proveedor,
        'procesarEdicionVariedad': Variedad,
        'cambiarEstadoVariedad': Variedad,
        'procesarEdicionFinca': Finca,
        'cambiarEstadoFinca': Finca,
        'procesarEdicionPersonal': Personal,
        'cambiarEstadoPersonal': Personal,
        'procesarEdicionRecepcion': Recepcion,
        'procesarEdicionClasificacion': Clasificacion,
        'procesarEdicionTarifario': Tarifario,
        'procesarEdicionLiquidacion': Liquidacion,
        'marcarLiquidacionPagada': Liquidacion,
        'procesarEdicionProveedorInsumo': ProveedorInsumo,
        'cambiarEstadoProveedorInsumo': ProveedorInsumo,
        'procesarEdicionCategoria': Categoria,
        'cambiarEstadoCategoria': Categoria,
        'procesarEdicionUnidadMedida': UnidadMedida,
        'cambiarEstadoUnidadMedida': UnidadMedida,
        'procesarEdicionProducto': Producto,
        'cambiarEstadoProducto': Producto,
    }
    model = registry.get(url_name)
    if not model:
        return None
    return model_snapshot(model.objects.filter(pk=identifier).first())
