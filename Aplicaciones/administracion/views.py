from datetime import date, datetime
from decimal import Decimal

from django.contrib import messages
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout, views as auth_views
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db.models import Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_encode
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from Aplicaciones.administracion.models import (
    DocumentoPersonal, Finca, PermisoPersonal, Personal, Proveedor, VacacionPersonal, Variedad,
)
from Aplicaciones.administracion.validators import (
    cedula_ecuatoriana_valida, ruc_ecuatoriano_valido, telefono_ecuatoriano_valido,
)
from Aplicaciones.auditoria.models import Bitacora
from FlorLY.security import (
    clear_login_failures, login_is_blocked, register_login_failure,
    security_cache_get, security_cache_set,
)
from FlorLY.file_security import validate_and_secure_document, validate_and_secure_image

User = get_user_model()
ROLES_SISTEMA = ('Administrador', 'Secretaria', 'Empleado')


@require_http_methods(['GET', 'POST'])
def iniciarSesion(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        if login_is_blocked(request, username):
            messages.error(request, 'Acceso bloqueado durante 15 minutos por múltiples intentos fallidos')
            return render(request, 'seguridad/login.html', status=429)
        user = authenticate(request, username=username, password=password)
        if user is None:
            intentos = register_login_failure(request, username)
            messages.error(request, f'Credenciales incorrectas. Intento {intentos} de 5')
        else:
            clear_login_failures(request, username)
            login(request, user)
            Bitacora.objects.create(
                usuario=user,
                accion='INICIO_SESION',
                tabla_afectada='seguridad',
                codigo_registro=str(user.pk),
                descripcion='Inicio de sesión correcto',
                direccion_ip=request.META.get('REMOTE_ADDR'),
            )
            destino = request.POST.get('next', '')
            if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
                destino = 'inicioSistema'
            return redirect(destino)
    return render(request, 'seguridad/login.html', {'next': request.GET.get('next', '')})


@require_POST
def cerrarSesion(request):
    logout(request)
    return redirect('login')


@require_http_methods(['GET', 'POST'])
def solicitarRecuperacion(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        if not settings.EMAIL_HOST_PASSWORD:
            messages.error(request, 'El correo de recuperación todavía no está configurado en el servidor.')
            return redirect('recuperarCredenciales')
        ip = request.META.get('REMOTE_ADDR', 'unknown')
        limite_key = f'recuperacion:{ip}:{username.lower()[:150]}'
        intentos = security_cache_get(limite_key, 0)
        if intentos >= 3:
            messages.warning(request, 'Espere 15 minutos antes de solicitar otro enlace.')
            return redirect('recuperarCredencialesEnviado')
        security_cache_set(limite_key, intentos + 1, 900)

        usuario = User.objects.filter(username__iexact=username, is_active=True).first()
        if usuario:
            uid = urlsafe_base64_encode(force_bytes(usuario.pk))
            token = default_token_generator.make_token(usuario)
            enlace = request.build_absolute_uri(
                reverse('restablecerCredencial', kwargs={'uidb64': uid, 'token': token})
            )
            cuerpo = render_to_string('seguridad/correoRecuperacion.txt', {
                'usuario': usuario,
                'enlace': enlace,
                'minutos': settings.PASSWORD_RESET_TIMEOUT // 60,
            })
            try:
                send_mail(
                    subject=f'Recuperación de acceso: {usuario.username}',
                    message=cuerpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.PASSWORD_RECOVERY_EMAIL],
                    fail_silently=False,
                )
                Bitacora.objects.create(
                    usuario=usuario,
                    accion='SOLICITUD_RECUPERACION',
                    tabla_afectada='seguridad',
                    codigo_registro=str(usuario.pk),
                    descripcion='Se envió un enlace de recuperación al correo institucional',
                    direccion_ip=request.META.get('REMOTE_ADDR'),
                )
            except Exception:
                messages.error(request, 'No se pudo enviar el correo. Revise la configuración institucional.')
                return redirect('recuperarCredenciales')
        return redirect('recuperarCredencialesEnviado')
    return render(request, 'seguridad/solicitarRecuperacion.html')


def recuperacionEnviada(request):
    return render(request, 'seguridad/recuperacionEnviada.html')


class RestablecerCredencialView(auth_views.PasswordResetConfirmView):
    template_name = 'seguridad/restablecerCredencial.html'
    success_url = reverse_lazy('restablecerCredencialCompleto')
    post_reset_login = False

    def form_valid(self, form):
        Bitacora.objects.create(
            usuario=self.user,
            accion='CREDENCIAL_RESTABLECIDA',
            tabla_afectada='seguridad',
            codigo_registro=str(self.user.pk),
            descripcion='La contraseña fue restablecida mediante enlace institucional',
            direccion_ip=self.request.META.get('REMOTE_ADDR'),
        )
        return super().form_valid(form)


def restablecimientoCompleto(request):
    return render(request, 'seguridad/restablecimientoCompleto.html')


def inicioUsuario(request):
    return render(request, 'seguridad/inicioUsuario.html', {
        'usuarios': User.objects.prefetch_related('groups').order_by('username'),
    })


def nuevoUsuario(request):
    return render(request, 'seguridad/nuevoUsuario.html', {'roles': ROLES_SISTEMA})


@require_POST
def guardarUsuario(request):
    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    rol = request.POST.get('rol', '')
    if rol not in ROLES_SISTEMA or User.objects.filter(username__iexact=username).exists():
        messages.error(request, 'El usuario ya existe o el rol no es válido')
        return redirect('nuevoUsuario')
    if password != request.POST.get('password_confirmacion', ''):
        messages.error(request, 'Las contraseñas no coinciden')
        return redirect('nuevoUsuario')
    try:
        validate_password(password)
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
        return redirect('nuevoUsuario')
    grupo, _ = Group.objects.get_or_create(name=rol)
    usuario = User.objects.create_user(
        username=username,
        password=password,
        first_name=request.POST.get('nombre', '').strip(),
        last_name=request.POST.get('apellido', '').strip(),
    )
    usuario.groups.set([grupo])
    messages.success(request, 'Usuario y credenciales creados correctamente')
    return redirect('inicioUsuario')


def editarUsuario(request, id):
    usuario = get_object_or_404(User.objects.prefetch_related('groups'), pk=id)
    return render(request, 'seguridad/editarUsuario.html', {
        'usuarioEditar': usuario,
        'rol_usuario': 'Administrador' if usuario.is_superuser else usuario.groups.values_list('name', flat=True).first(),
        'roles': ROLES_SISTEMA,
    })


@require_POST
def procesarUsuario(request):
    usuario = get_object_or_404(User, pk=request.POST['id'])
    rol = request.POST.get('rol', '')
    if rol not in ROLES_SISTEMA:
        messages.error(request, 'Rol no válido')
        return redirect('editarUsuario', id=usuario.pk)
    activo = request.POST.get('is_active') == 'on'
    if usuario == request.user and (not activo or rol != 'Administrador'):
        messages.error(request, 'No puede desactivar ni retirar su propio acceso de administrador')
        return redirect('editarUsuario', id=usuario.pk)
    if usuario.is_superuser and (not activo or rol != 'Administrador'):
        messages.error(request, 'Una cuenta superadministradora no puede degradarse desde esta pantalla')
        return redirect('editarUsuario', id=usuario.pk)
    grupo, _ = Group.objects.get_or_create(name=rol)
    usuario.first_name = request.POST.get('nombre', '').strip()
    usuario.last_name = request.POST.get('apellido', '').strip()
    usuario.is_active = activo
    usuario.groups.set([grupo])
    password = request.POST.get('password', '')
    if password:
        if password != request.POST.get('password_confirmacion', ''):
            messages.error(request, 'Las contraseñas no coinciden')
            return redirect('editarUsuario', id=usuario.pk)
        try:
            validate_password(password, user=usuario)
        except ValidationError as error:
            messages.error(request, ' '.join(error.messages))
            return redirect('editarUsuario', id=usuario.pk)
        usuario.set_password(password)
    usuario.save()
    messages.success(request, 'Acceso del usuario actualizado')
    return redirect('inicioUsuario')


def inicioSistema(request):
    ahora = timezone.localtime()
    es_empleado = request.user.groups.filter(name='Empleado').exists()
    if not es_empleado and ahora.hour >= 15:
        from Aplicaciones.liquidaciones.services import generar_liquidaciones_vencidas
        generadas, errores = generar_liquidaciones_vencidas(ahora.date())
        if generadas:
            messages.success(request, f'{len(generadas)} reporte(s) mensual(es) se generaron automáticamente.')
        for error in errores:
            messages.error(request, f'Liquidación pendiente: {error}')
    contexto = {
        'total_proveedores': Proveedor.objects.filter(estado=True).count(),
        'total_variedades': Variedad.objects.filter(estado=True).count(),
        'total_fincas': Finca.objects.filter(estado=True).count(),
        'total_personal': Personal.objects.filter(estado=True).count(),
    }
    vacaciones = VacacionPersonal.objects.filter(
        personal__estado=True,
    ).select_related('personal').order_by(
        'fecha_desde', 'personal__apellidos', 'personal__nombres',
    )
    contexto['vacaciones_dashboard'] = [
        {
            'id': vacacion.pk,
            'personal': f'{vacacion.personal.nombres} {vacacion.personal.apellidos}',
            'area': vacacion.personal.area,
            'desde': vacacion.fecha_desde.isoformat(),
            'hasta': vacacion.fecha_hasta.isoformat(),
        }
        for vacacion in vacaciones
    ]
    contexto['hoy_dashboard'] = ahora.date().isoformat()
    from Aplicaciones.postcosecha.models import DetalleClasificacion, DetalleRecepcion

    meses = []
    cursor = date(ahora.year, ahora.month, 1)
    for desplazamiento in range(5, -1, -1):
        indice = cursor.year * 12 + cursor.month - 1 - desplazamiento
        meses.append(date(indice // 12, indice % 12 + 1, 1))
    recibidos_por_mes = {mes: 0 for mes in meses}
    clasificados_por_mes = {mes: 0 for mes in meses}
    for fecha_recepcion, mallas, tallos_malla in DetalleRecepcion.objects.filter(
        recepcion__fecha_recepcion__date__gte=meses[0]
    ).values_list('recepcion__fecha_recepcion', 'cantidad_mallas', 'tallos_por_malla'):
        fecha_local = timezone.localtime(fecha_recepcion)
        clave = date(fecha_local.year, fecha_local.month, 1)
        if clave in recibidos_por_mes:
            recibidos_por_mes[clave] += mallas * tallos_malla
    for fecha_clasificacion, exportables, nacionales, sobrantes in DetalleClasificacion.objects.filter(
        clasificacion__fecha_clasificacion__gte=meses[0]
    ).values_list(
        'clasificacion__fecha_clasificacion', 'tallos_exportables',
        'tallos_nacionales', 'tallos_sobrantes',
    ):
        clave = date(fecha_clasificacion.year, fecha_clasificacion.month, 1)
        if clave in clasificados_por_mes:
            clasificados_por_mes[clave] += exportables + nacionales + sobrantes

    nombres_meses = ('Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic')
    calidad = DetalleClasificacion.objects.filter(
        clasificacion__fecha_clasificacion__year=ahora.year
    ).aggregate(
        optimos=Sum('tallos_exportables', filter=Q(largo='OPTIMO')),
        estandar=Sum('tallos_exportables', filter=Q(largo='ESTANDAR')),
        nacionales=Sum('tallos_nacionales'),
    )
    origen = DetalleRecepcion.objects.filter(
        recepcion__fecha_recepcion__year=ahora.year
    ).values_list(
        'recepcion__proveedor_id', 'recepcion__finca_id',
        'cantidad_mallas', 'tallos_por_malla',
    )
    tallos_proveedor = 0
    tallos_finca = 0
    for proveedor_id, finca_id, mallas, tallos_malla in origen:
        if proveedor_id:
            tallos_proveedor += mallas * tallos_malla
        elif finca_id:
            tallos_finca += mallas * tallos_malla

    contexto['graficos_dashboard'] = {
        'tendencia': {
            'etiquetas': [f'{nombres_meses[mes.month - 1]} {mes.year}' for mes in meses],
            'recibidos': [recibidos_por_mes[mes] for mes in meses],
            'clasificados': [clasificados_por_mes[mes] for mes in meses],
        },
        'calidad': {
            'etiquetas': ['Óptimos', 'Estándar', 'Nacionales'],
            'valores': [calidad['optimos'] or 0, calidad['estandar'] or 0, calidad['nacionales'] or 0],
        },
        'origen': {
            'etiquetas': ['Proveedores', 'Finca propia'],
            'valores': [tallos_proveedor, tallos_finca],
        },
    }
    if not es_empleado:
        from Aplicaciones.liquidaciones.models import Liquidacion
        totales_liquidacion = Liquidacion.objects.aggregate(
            pagadas=Sum('total', filter=Q(estado='PAGADA')),
            pendientes=Sum('total', filter=Q(estado__in=('PEND_DOCUMENTO', 'PEND_PAGO'))),
        )
        contexto['graficos_dashboard']['liquidaciones'] = {
            'etiquetas': ['Pagadas', 'Pendientes'],
            'valores': [
                float(totales_liquidacion['pagadas'] or 0),
                float(totales_liquidacion['pendientes'] or 0),
            ],
        }
    return render(request, 'inicioSistema.html', contexto)


def _generar_codigo(modelo, campo, prefijo, longitud=4):
    ultimo = modelo.objects.order_by(f'-{campo}').values_list(campo, flat=True).first()
    numero = int(ultimo[len(prefijo):]) + 1 if ultimo else 1
    return f'{prefijo}{numero:0{longitud}d}'


def _documento_identidad_valido(valor, tipo='CEDULA'):
    return ruc_ecuatoriano_valido(valor) if tipo == 'RUC' else cedula_ecuatoriana_valida(valor)


# Proveedores de flores
def inicioProveedor(request):
    return render(request, 'proveedores/inicioProveedor.html', {
        'proveedores': Proveedor.objects.all().order_by('apellidos', 'nombres')
    })


def nuevoProveedor(request):
    return render(request, 'proveedores/nuevoProveedor.html')


@require_POST
def guardarProveedor(request):
    cedula_ruc = request.POST.get('cedula_ruc', '').strip()
    telefono = request.POST.get('telefono', '').strip()
    tipo_documento = 'RUC' if len(cedula_ruc) == 13 else 'CEDULA'
    if len(cedula_ruc) not in (10, 13) or not _documento_identidad_valido(cedula_ruc, tipo_documento):
        messages.error(request, 'Ingrese una cédula de 10 dígitos o un RUC de 13 dígitos válido')
        return redirect('nuevoProveedor')
    if Proveedor.objects.filter(cedula_ruc=cedula_ruc).exists():
        messages.error(request, 'Ya existe un proveedor registrado con esa cédula o RUC')
        return redirect('nuevoProveedor')
    if not telefono_ecuatoriano_valido(telefono):
        messages.error(request, 'Ingrese un celular nacional 09 de 10 dígitos o un teléfono local de 7 dígitos')
        return redirect('nuevoProveedor')
    Proveedor.objects.create(
        codigo_proveedor=_generar_codigo(Proveedor, 'codigo_proveedor', 'PR'),
        nombres=request.POST['nombres'].strip().upper(),
        apellidos=request.POST['apellidos'].strip().upper(),
        cedula_ruc=cedula_ruc,
        telefono=telefono,
    )
    messages.success(request, 'Proveedor guardado exitosamente')
    return redirect('/proveedores')


def editarProveedor(request, codigo):
    return render(request, 'proveedores/editarProveedor.html', {
        'proveedorEditar': get_object_or_404(Proveedor, pk=codigo)
    })


@require_POST
def procesarEdicionProveedor(request):
    proveedor = get_object_or_404(Proveedor, pk=request.POST['codigo_proveedor'])
    cedula_ruc = request.POST.get('cedula_ruc', '').strip()
    telefono = request.POST.get('telefono', '').strip()
    tipo_documento = 'RUC' if len(cedula_ruc) == 13 else 'CEDULA'
    if len(cedula_ruc) not in (10, 13) or not _documento_identidad_valido(cedula_ruc, tipo_documento):
        messages.error(request, 'Ingrese una cédula de 10 dígitos o un RUC de 13 dígitos válido')
        return redirect('editarProveedor', codigo=proveedor.pk)
    if Proveedor.objects.filter(cedula_ruc=cedula_ruc).exclude(pk=proveedor.pk).exists():
        messages.error(request, 'La cédula o RUC ya pertenece a otro proveedor')
        return redirect('editarProveedor', codigo=proveedor.pk)
    if not telefono_ecuatoriano_valido(telefono):
        messages.error(request, 'Ingrese un celular nacional 09 de 10 dígitos o un teléfono local de 7 dígitos')
        return redirect('editarProveedor', codigo=proveedor.pk)
    proveedor.nombres = request.POST['nombres'].strip().upper()
    proveedor.apellidos = request.POST['apellidos'].strip().upper()
    proveedor.cedula_ruc = cedula_ruc
    proveedor.telefono = telefono
    proveedor.save()
    messages.success(request, 'Proveedor actualizado exitosamente')
    return redirect('/proveedores')


@require_POST
def cambiarEstadoProveedor(request, codigo):
    proveedor = get_object_or_404(Proveedor, pk=codigo)
    proveedor.estado = not proveedor.estado
    proveedor.save()
    messages.success(request, 'Estado del proveedor actualizado exitosamente')
    return redirect('/proveedores')


# Variedades
def inicioVariedad(request):
    return render(request, 'variedades/inicioVariedad.html', {
        'variedades': Variedad.objects.all().order_by('nombre')
    })


def nuevaVariedad(request):
    return render(request, 'variedades/nuevaVariedad.html')


@require_POST
def guardarVariedad(request):
    imagen = request.FILES.get('imagen')
    if not imagen:
        messages.error(request, 'Seleccione una imagen JPG o PNG para la variedad')
        return redirect('nuevaVariedad')
    try:
        validate_and_secure_image(imagen)
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
        return redirect('nuevaVariedad')
    Variedad.objects.create(
        codigo_variedad=_generar_codigo(Variedad, 'codigo_variedad', 'VAR'),
        nombre=request.POST['nombre'].strip().upper(),
        imagen=imagen,
    )
    messages.success(request, 'Variedad guardada exitosamente')
    return redirect('inicioVariedad')


def editarVariedad(request, codigo):
    return render(request, 'variedades/editarVariedad.html', {
        'variedadEditar': get_object_or_404(Variedad, pk=codigo)
    })


@require_POST
def procesarEdicionVariedad(request):
    variedad = get_object_or_404(Variedad, pk=request.POST['codigo_variedad'])
    variedad.nombre = request.POST['nombre'].strip().upper()
    nueva_imagen = request.FILES.get('imagen')
    imagen_anterior = variedad.imagen.name if variedad.imagen else None
    if nueva_imagen:
        try:
            validate_and_secure_image(nueva_imagen)
        except ValidationError as error:
            messages.error(request, ' '.join(error.messages))
            return redirect('editarVariedad', codigo=variedad.pk)
        variedad.imagen = nueva_imagen
    elif not variedad.imagen:
        messages.error(request, 'Seleccione una imagen JPG o PNG para la variedad')
        return redirect('editarVariedad', codigo=variedad.pk)
    variedad.save()
    if nueva_imagen and imagen_anterior and imagen_anterior != variedad.imagen.name:
        variedad.imagen.storage.delete(imagen_anterior)
    messages.success(request, 'Variedad actualizada exitosamente')
    return redirect('inicioVariedad')


def imagenVariedad(request, codigo):
    variedad = get_object_or_404(Variedad, pk=codigo)
    if not variedad.imagen:
        raise Http404('Imagen no encontrada')
    try:
        return FileResponse(
            variedad.imagen.open('rb'),
            content_type='image/png' if variedad.imagen.name.lower().endswith('.png') else 'image/jpeg',
        )
    except FileNotFoundError as error:
        raise Http404('Imagen no encontrada') from error


@require_POST
def cambiarEstadoVariedad(request, codigo):
    variedad = get_object_or_404(Variedad, pk=codigo)
    variedad.estado = not variedad.estado
    variedad.save()
    messages.success(request, 'Estado de la variedad actualizado exitosamente')
    return redirect('inicioVariedad')


# Fincas
def inicioFinca(request):
    return render(request, 'fincas/inicioFinca.html', {
        'fincas': Finca.objects.all().order_by('nombre')
    })


def nuevaFinca(request):
    return render(request, 'fincas/nuevaFinca.html')


@require_POST
def guardarFinca(request):
    Finca.objects.create(
        codigo_finca=_generar_codigo(Finca, 'codigo_finca', 'FIN'),
        nombre=request.POST['nombre'].strip().upper(),
        ubicacion=request.POST['ubicacion'].strip(),
    )
    messages.success(request, 'Finca guardada exitosamente')
    return redirect('/fincas')


def editarFinca(request, codigo):
    return render(request, 'fincas/editarFinca.html', {
        'fincaEditar': get_object_or_404(Finca, pk=codigo)
    })


@require_POST
def procesarEdicionFinca(request):
    finca = get_object_or_404(Finca, pk=request.POST['codigo_finca'])
    finca.nombre = request.POST['nombre'].strip().upper()
    finca.ubicacion = request.POST['ubicacion'].strip()
    finca.save()
    messages.success(request, 'Finca actualizada exitosamente')
    return redirect('/fincas')


@require_POST
def cambiarEstadoFinca(request, codigo):
    finca = get_object_or_404(Finca, pk=codigo)
    finca.estado = not finca.estado
    finca.save()
    messages.success(request, 'Estado de la finca actualizado exitosamente')
    return redirect('/fincas')


# Personal
def inicioPersonal(request):
    personal = list(Personal.objects.select_related('finca').all().order_by('apellidos', 'nombres'))
    return render(request, 'personal/inicioPersonal.html', {
        'personal': personal,
        'personal_con_vacaciones': [p for p in personal if p.estado and p.tiene_derecho_vacaciones],
    })


def nuevoPersonal(request):
    return render(request, 'personal/nuevoPersonal.html', {
        'fincas': Finca.objects.filter(estado=True).order_by('nombre')
    })


@require_POST
def guardarPersonal(request):
    finca = get_object_or_404(Finca, pk=request.POST['finca'])
    cedula = request.POST.get('cedula', '').strip()
    telefono = request.POST.get('telefono', '').strip()
    if not _documento_identidad_valido(cedula):
        messages.error(request, 'La cédula ingresada no cumple la estructura ecuatoriana')
        return redirect('nuevoPersonal')
    if Personal.objects.filter(cedula=cedula).exists():
        messages.error(request, 'Ya existe un empleado registrado con esa cédula')
        return redirect('nuevoPersonal')
    if not telefono_ecuatoriano_valido(telefono):
        messages.error(request, 'Ingrese un celular nacional 09 de 10 dígitos o un teléfono local de 7 dígitos')
        return redirect('nuevoPersonal')
    Personal.objects.create(
        codigo_personal=_generar_codigo(Personal, 'codigo_personal', 'PER'),
        nombres=request.POST['nombres'].strip().upper(),
        apellidos=request.POST['apellidos'].strip().upper(),
        cedula=cedula,
        telefono=telefono,
        fecha_ingreso=request.POST['fecha_ingreso'],
        area=request.POST['area'].strip(),
        finca=finca,
    )
    messages.success(request, 'Personal guardado exitosamente')
    return redirect('/personal')


def editarPersonal(request, codigo):
    return render(request, 'personal/editarPersonal.html', {
        'personalEditar': get_object_or_404(Personal, pk=codigo),
        'fincas': Finca.objects.filter(estado=True).order_by('nombre'),
    })


@require_POST
def procesarEdicionPersonal(request):
    persona = get_object_or_404(Personal, pk=request.POST['codigo_personal'])
    cedula = request.POST.get('cedula', '').strip()
    telefono = request.POST.get('telefono', '').strip()
    if not _documento_identidad_valido(cedula):
        messages.error(request, 'La cédula ingresada no cumple la estructura ecuatoriana')
        return redirect('editarPersonal', codigo=persona.pk)
    if Personal.objects.filter(cedula=cedula).exclude(pk=persona.pk).exists():
        messages.error(request, 'La cédula ya pertenece a otro empleado')
        return redirect('editarPersonal', codigo=persona.pk)
    if not telefono_ecuatoriano_valido(telefono):
        messages.error(request, 'Ingrese un celular nacional 09 de 10 dígitos o un teléfono local de 7 dígitos')
        return redirect('editarPersonal', codigo=persona.pk)
    persona.nombres = request.POST['nombres'].strip().upper()
    persona.apellidos = request.POST['apellidos'].strip().upper()
    persona.cedula = cedula
    persona.telefono = telefono
    persona.fecha_ingreso = request.POST['fecha_ingreso']
    persona.area = request.POST['area'].strip()
    persona.finca = get_object_or_404(Finca, pk=request.POST['finca'])
    persona.save()
    messages.success(request, 'Personal actualizado exitosamente')
    return redirect('/personal')


@require_POST
def cambiarEstadoPersonal(request, codigo):
    persona = get_object_or_404(Personal, pk=codigo)
    persona.estado = not persona.estado
    persona.save()
    messages.success(request, 'Estado del personal actualizado exitosamente')
    return redirect('/personal')


def expedientePersonal(request, codigo):
    persona = get_object_or_404(Personal.objects.select_related('finca'), pk=codigo)
    return render(request, 'personal/expedientePersonal.html', {
        'persona': persona,
        'permisos': persona.permisos.all().order_by('-fecha_desde', '-fecha_registro'),
        'vacaciones': persona.vacaciones.all().order_by('-fecha_desde', '-fecha_registro'),
        'documentos': persona.documentos.all().order_by('-fecha_documento', '-fecha_registro'),
        'motivos_permiso': PermisoPersonal.MOTIVOS,
    })


@require_POST
def guardarPermisoPersonal(request, codigo):
    persona = get_object_or_404(Personal, pk=codigo)
    try:
        fecha_desde = datetime.strptime(request.POST['fecha_desde'], '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(request.POST['fecha_hasta'], '%Y-%m-%d').date()
        if fecha_hasta < fecha_desde:
            raise ValueError('La fecha final no puede ser anterior a la inicial')
        hora_salida_texto = request.POST.get('hora_salida', '')
        hora_retorno_texto = request.POST.get('hora_retorno', '')
        hora_salida = datetime.strptime(hora_salida_texto, '%H:%M').time() if hora_salida_texto else None
        hora_retorno = datetime.strptime(hora_retorno_texto, '%H:%M').time() if hora_retorno_texto else None
        if bool(hora_salida) != bool(hora_retorno):
            raise ValueError('Debe ingresar tanto la hora de salida como la de retorno')
        if fecha_desde == fecha_hasta and hora_salida and hora_retorno:
            minutos = (
                datetime.combine(fecha_hasta, hora_retorno)
                - datetime.combine(fecha_desde, hora_salida)
            ).total_seconds() / 60
            if minutos <= 0:
                raise ValueError('La hora de retorno debe ser posterior a la hora de salida')
            dias_descontados = (Decimal(str(minutos)) / Decimal('480')).quantize(Decimal('0.01'))
        else:
            dias_descontados = Decimal((fecha_hasta - fecha_desde).days + 1)
        if dias_descontados > persona.saldo_vacaciones:
            raise ValueError(f'El permiso supera el saldo disponible de {persona.saldo_vacaciones} días')
    except (KeyError, ValueError) as error:
        messages.error(request, str(error))
        return redirect('expedientePersonal', codigo=persona.pk)

    PermisoPersonal.objects.create(
        personal=persona,
        motivo=request.POST['motivo'],
        observacion=request.POST.get('observacion', '').strip(),
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        hora_salida=hora_salida,
        hora_retorno=hora_retorno,
        dias_descontados=dias_descontados,
    )
    messages.success(request, f'Permiso registrado. Se descontaron {dias_descontados} días de vacaciones')
    return redirect('expedientePersonal', codigo=persona.pk)


@require_POST
def guardarVacacionPersonal(request, codigo):
    persona = get_object_or_404(Personal, pk=codigo)
    try:
        fecha_desde = datetime.strptime(request.POST['fecha_desde'], '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(request.POST['fecha_hasta'], '%Y-%m-%d').date()
        if fecha_hasta < fecha_desde:
            raise ValueError('La fecha final no puede ser anterior a la inicial')
        dias = (fecha_hasta - fecha_desde).days + 1
        if Decimal(dias) > persona.saldo_vacaciones:
            raise ValueError(f'Las vacaciones superan el saldo disponible de {persona.saldo_vacaciones} días')
    except (KeyError, ValueError) as error:
        messages.error(request, str(error))
        return redirect('expedientePersonal', codigo=persona.pk)
    VacacionPersonal.objects.create(
        personal=persona,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        dias_tomados=dias,
        observacion=request.POST.get('observacion', '').strip(),
    )
    messages.success(request, f'Vacaciones registradas: {dias} días descontados')
    return redirect('expedientePersonal', codigo=persona.pk)


@require_POST
def guardarDocumentoPersonal(request, codigo):
    persona = get_object_or_404(Personal, pk=codigo)
    archivo = request.FILES.get('archivo')
    if not archivo:
        messages.error(request, 'Seleccione un archivo para el documento')
        return redirect('expedientePersonal', codigo=persona.pk)
    try:
        archivo = validate_and_secure_document(archivo)
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
        return redirect('expedientePersonal', codigo=persona.pk)
    DocumentoPersonal.objects.create(
        personal=persona,
        nombre=request.POST['nombre'].strip(),
        archivo=archivo,
        observacion=request.POST.get('observacion', '').strip(),
    )
    messages.success(request, 'Documento agregado al expediente')
    return redirect('expedientePersonal', codigo=persona.pk)
