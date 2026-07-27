import logging

from django.core.cache import cache, caches
from django.shortcuts import redirect, render
from django.urls import Resolver404, resolve, reverse

from FlorLY.audit_helpers import (
    entity_from_path, readable_action, record_identifier, safe_request_data,
    snapshot_for_action,
)


audit_logger = logging.getLogger('FlorLY.audit')

PUBLIC_URL_NAMES = {
    'login', 'recuperarCredenciales', 'recuperarCredencialesEnviado',
    'restablecerCredencial', 'restablecerCredencialCompleto',
}

EMPLOYEE_URL_NAMES = {
    'inicioSistema',
    'inicioProveedor', 'nuevoProveedor', 'guardarProveedor', 'editarProveedor', 'procesarEdicionProveedor',
    'inicioVariedad', 'nuevaVariedad', 'guardarVariedad', 'editarVariedad', 'procesarEdicionVariedad',
    'inicioRecepcion', 'nuevaRecepcion', 'guardarRecepcion', 'ticketRecepcion', 'detalleRecepcion',
    'editarRecepcion', 'procesarEdicionRecepcion', 'guardarDetalleRecepcion',
    'procesarEdicionDetalleRecepcion', 'eliminarDetalleRecepcion',
    'inicioClasificacion', 'reporteDiarioClasificacion', 'nuevaClasificacion', 'guardarClasificacion', 'reporteClasificacion',
    'editarClasificacion', 'procesarEdicionClasificacion',
    'logout',
}

SECRETARY_URL_NAMES = {
    'inicioSistema',
    'inicioProveedor', 'nuevoProveedor', 'guardarProveedor', 'editarProveedor', 'procesarEdicionProveedor',
    'inicioVariedad', 'nuevaVariedad', 'guardarVariedad', 'editarVariedad', 'procesarEdicionVariedad',
    'inicioFinca', 'nuevaFinca', 'guardarFinca', 'editarFinca', 'procesarEdicionFinca',
    'inicioPersonal', 'nuevoPersonal', 'guardarPersonal', 'editarPersonal', 'procesarEdicionPersonal',
    'expedientePersonal', 'guardarPermisoPersonal', 'guardarVacacionPersonal', 'guardarDocumentoPersonal',
    'inicioLiquidacion', 'nuevaLiquidacion', 'guardarLiquidacion', 'verLiquidacion',
    'editarLiquidacion', 'procesarEdicionLiquidacion',
    'logout',
}


def user_role(user):
    if user.is_superuser or user.groups.filter(name='Administrador').exists():
        return 'ADMINISTRADOR'
    if user.groups.filter(name='Secretaria').exists():
        return 'SECRETARIA'
    if user.groups.filter(name='Empleado').exists():
        return 'EMPLEADO'
    return 'SIN_ROL'


def _write_denied_audit(request, match, role):
    try:
        from Aplicaciones.auditoria.models import Bitacora
        Bitacora.objects.create(
            usuario=request.user,
            accion='ACCESO DENEGADO',
            tabla_afectada=entity_from_path(request.path_info),
            codigo_registro=record_identifier(match, request)[:20],
            descripcion=f'Intento de acceso sin autorización con rol {role}.',
            direccion_ip=request.META.get('REMOTE_ADDR'),
            metodo=request.method,
            ruta=request.path_info[:255],
            resultado='RECHAZADA',
            datos_nuevos=safe_request_data(request) if request.method == 'POST' else None,
        )
    except Exception:
        audit_logger.exception('No se pudo registrar un acceso denegado a %s', request.path_info)


class RoleAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            match = resolve(request.path_info)
            url_name = match.url_name
            namespace = match.namespace
        except Resolver404:
            return self.get_response(request)

        if url_name in PUBLIC_URL_NAMES:
            if url_name == 'login' and request.user.is_authenticated:
                return redirect('inicioSistema')
            return self.get_response(request)
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.get_full_path()}")
        if url_name == 'logout':
            return self.get_response(request)

        role = user_role(request.user)
        allowed = role == 'ADMINISTRADOR'
        if role == 'SECRETARIA':
            allowed = url_name in SECRETARY_URL_NAMES and namespace != 'admin'
        elif role == 'EMPLEADO':
            allowed = url_name in EMPLOYEE_URL_NAMES and namespace != 'admin'
        if not allowed:
            _write_denied_audit(request, match, role)
            return render(request, '403.html', status=403)

        identifier = record_identifier(match, request)
        previous_data = None
        if request.method == 'POST':
            try:
                previous_data = snapshot_for_action(url_name, identifier)
            except Exception:
                audit_logger.exception('No se pudo obtener el estado anterior para %s', url_name)

        response = self.get_response(request)
        if request.method == 'POST' and response.status_code < 400 and url_name != 'logout':
            try:
                from Aplicaciones.auditoria.models import Bitacora
                current_data = snapshot_for_action(url_name, identifier)
                Bitacora.objects.create(
                    usuario=request.user,
                    accion=readable_action(url_name),
                    tabla_afectada=entity_from_path(request.path_info),
                    codigo_registro=identifier[:20],
                    descripcion=f'Operación autorizada y procesada: {readable_action(url_name).lower()}.',
                    direccion_ip=request.META.get('REMOTE_ADDR'),
                    metodo=request.method,
                    ruta=request.path_info[:255],
                    resultado='PROCESADA',
                    datos_anteriores=previous_data,
                    datos_nuevos=current_data or safe_request_data(request),
                )
            except Exception:
                audit_logger.exception(
                    'FALLO DE AUDITORÍA: operación %s en %s realizada por usuario %s',
                    url_name, request.path_info, request.user.pk,
                )
        return response


def security_context(request):
    role = user_role(request.user) if request.user.is_authenticated else None
    return {
        'rol_actual': role,
        'es_administrador': role == 'ADMINISTRADOR',
        'es_secretaria': role == 'SECRETARIA',
        'es_empleado': role == 'EMPLEADO',
    }


def login_cache_key(request, username):
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    return f"login-fail:{ip}:{username.lower()[:150]}"


def login_ip_cache_key(request):
    return f"login-fail-ip:{request.META.get('REMOTE_ADDR', 'unknown')}"


def security_cache_get(key, default=None):
    try:
        return cache.get(key, default)
    except Exception:
        audit_logger.exception('Valkey no está disponible al consultar la clave de seguridad %s', key)
        return caches['local_fallback'].get(key, default)


def security_cache_set(key, value, timeout=900):
    try:
        cache.set(key, value, timeout)
    except Exception:
        audit_logger.exception('Valkey no está disponible al guardar una clave de seguridad')
    caches['local_fallback'].set(key, value, timeout)


def security_cache_delete(key):
    try:
        cache.delete(key)
    except Exception:
        audit_logger.exception('Valkey no está disponible al eliminar una clave de seguridad')
    caches['local_fallback'].delete(key)


def security_cache_increment(key, timeout=900):
    try:
        cache.add(key, 0, timeout)
        value = cache.incr(key)
        cache.touch(key, timeout)
        caches['local_fallback'].set(key, value, timeout)
        return value
    except Exception:
        audit_logger.exception('Valkey no está disponible al incrementar una clave de seguridad')
        fallback = caches['local_fallback']
        fallback.add(key, 0, timeout)
        value = fallback.incr(key)
        fallback.touch(key, timeout)
        return value


def register_login_failure(request, username):
    key = login_cache_key(request, username)
    failures = security_cache_increment(key, 900)
    ip_key = login_ip_cache_key(request)
    security_cache_increment(ip_key, 900)
    return failures


def clear_login_failures(request, username):
    security_cache_delete(login_cache_key(request, username))
    security_cache_delete(login_ip_cache_key(request))


def login_is_blocked(request, username):
    return (
        security_cache_get(login_cache_key(request, username), 0) >= 5
        or security_cache_get(login_ip_cache_key(request), 0) >= 10
    )
