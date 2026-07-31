from datetime import date, timedelta
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from FlorLY.file_security import (
    MAX_DOCUMENT_SIZE, validate_and_secure_document, validate_and_secure_image,
)
from FlorLY.security import (
    clear_login_failures, login_is_blocked, register_login_failure,
)
from Aplicaciones.administracion.models import (
    DocumentoPersonal, Finca, PermisoPersonal, Personal, Proveedor, VacacionPersonal, Variedad,
)
from Aplicaciones.liquidaciones.models import Liquidacion


class SeguridadArchivosTests(SimpleTestCase):
    def test_acepta_pdf_real_y_cambia_nombre(self):
        archivo = SimpleUploadedFile(
            'documento personal.pdf', b'%PDF-1.7\ncontenido', content_type='application/pdf'
        )
        validate_and_secure_document(archivo)
        self.assertRegex(archivo.name, r'^[0-9a-f]{32}\.pdf$')

    def test_rechaza_ejecutable_disfrazado_de_pdf(self):
        archivo = SimpleUploadedFile(
            'documento.pdf', b'MZ\x90\x00programa', content_type='application/pdf'
        )
        with self.assertRaises(ValidationError):
            validate_and_secure_document(archivo)

    def test_rechaza_tipo_declarado_incorrecto(self):
        archivo = SimpleUploadedFile(
            'imagen.png', b'\x89PNG\r\n\x1a\ncontenido', content_type='application/octet-stream'
        )
        with self.assertRaises(ValidationError):
            validate_and_secure_document(archivo)

    def test_rechaza_archivo_mayor_a_cinco_mb(self):
        archivo = SimpleUploadedFile(
            'grande.pdf', b'%PDF-' + b'x' * MAX_DOCUMENT_SIZE, content_type='application/pdf'
        )
        with self.assertRaises(ValidationError):
            validate_and_secure_document(archivo)

    def test_acepta_imagen_png_y_protege_su_nombre(self):
        imagen = SimpleUploadedFile(
            'rosa freedom.png', b'\x89PNG\r\n\x1a\ncontenido', content_type='image/png'
        )
        validate_and_secure_image(imagen)
        self.assertRegex(imagen.name, r'^[0-9a-f]{32}\.png$')

    def test_rechaza_pdf_disfrazado_de_imagen(self):
        imagen = SimpleUploadedFile(
            'rosa.jpg', b'%PDF-1.7\ncontenido', content_type='image/jpeg'
        )
        with self.assertRaises(ValidationError):
            validate_and_secure_image(imagen)


class LimiteIntentosAccesoTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().post('/login/', REMOTE_ADDR='192.0.2.10')
        clear_login_failures(self.request, 'usuario_prueba')

    def tearDown(self):
        clear_login_failures(self.request, 'usuario_prueba')

    def test_bloquea_al_quinto_intento_y_limpia_al_ingresar(self):
        for _ in range(5):
            register_login_failure(self.request, 'usuario_prueba')
        self.assertTrue(login_is_blocked(self.request, 'usuario_prueba'))
        clear_login_failures(self.request, 'usuario_prueba')
        self.assertFalse(login_is_blocked(self.request, 'usuario_prueba'))


class GraficosDashboardTests(TestCase):
    def test_dashboard_administrador_renderiza_los_cuatro_graficos_sin_datos(self):
        usuario = get_user_model().objects.create_superuser(
            username='admin_dashboard', password='ClaveDashboard123!'
        )
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse('inicioSistema'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'graficoTendencia')
        self.assertContains(respuesta, 'graficoCalidad')
        self.assertContains(respuesta, 'graficoOrigen')
        self.assertContains(respuesta, 'graficoLiquidaciones')

    def test_dashboard_empleado_no_expone_datos_de_liquidaciones(self):
        usuario = get_user_model().objects.create_user(
            username='empleado_dashboard', password='ClaveDashboard123!'
        )
        grupo, _ = Group.objects.get_or_create(name='Empleado')
        usuario.groups.add(grupo)
        self.client.force_login(usuario)
        respuesta = self.client.get(reverse('inicioSistema'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, '<canvas id="graficoLiquidaciones"', html=False)
        self.assertNotIn('liquidaciones', respuesta.context['graficos_dashboard'])

    def test_dashboard_muestra_calendario_y_vacaciones_registradas(self):
        usuario = get_user_model().objects.create_superuser(
            username='admin_calendario', password='ClaveCalendario123!'
        )
        finca = Finca.objects.create(
            codigo_finca='FINTEST', nombre='FINCA PRUEBA', ubicacion='CAYAMBE'
        )
        personal = Personal.objects.create(
            codigo_personal='PERTEST', nombres='ANA MARIA', apellidos='LOPEZ VEGA',
            cedula='1710034065', telefono='0999999999', fecha_ingreso=date(2020, 1, 1),
            area='POSTCOSECHA', finca=finca,
        )
        VacacionPersonal.objects.create(
            personal=personal, fecha_desde=date(2026, 7, 20),
            fecha_hasta=date(2026, 7, 31), dias_tomados=12,
        )
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse('inicioSistema'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Calendario de vacaciones')
        self.assertContains(respuesta, 'datosVacacionesDashboard')
        self.assertNotContains(respuesta, 'Flujo de postcosecha')
        self.assertEqual(respuesta.context['vacaciones_dashboard'][0]['personal'], 'ANA MARIA LOPEZ VEGA')

    def test_campana_muestra_reporte_mensual_pendiente(self):
        usuario = get_user_model().objects.create_superuser(
            username='admin_notificaciones', password='ClaveNotificacion123!'
        )
        proveedor = Proveedor.objects.create(
            codigo_proveedor='PRONOT', nombres='ROSA', apellidos='FLORES',
            cedula_ruc='1710034065', telefono='0999999999',
        )
        Liquidacion.objects.create(
            codigo_liquidacion='LIQNOT001', proveedor=proveedor,
            fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 6, 30),
            fecha_liquidacion=date(2026, 7, 1), total='148.50',
            estado='PEND_DOCUMENTO',
        )
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse('inicioSistema'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'Reporte mensual listo')
        self.assertContains(respuesta, 'LIQNOT001')
        self.assertContains(respuesta, '$148,50')
        self.assertEqual(respuesta.context['total_notificaciones_reportes'], 1)


class ImagenVariedadTests(TestCase):
    def setUp(self):
        self.directorio_media = TemporaryDirectory()
        self.configuracion_media = override_settings(MEDIA_ROOT=self.directorio_media.name)
        self.configuracion_media.enable()
        usuario = get_user_model().objects.create_superuser(
            username='admin_variedad_imagen', password='ClaveImagen123!'
        )
        self.client.force_login(usuario)

    def tearDown(self):
        self.configuracion_media.disable()
        self.directorio_media.cleanup()

    def test_registra_y_muestra_imagen_de_variedad(self):
        imagen = SimpleUploadedFile(
            'freedom.png', b'\x89PNG\r\n\x1a\ncontenido', content_type='image/png'
        )

        respuesta = self.client.post(reverse('guardarVariedad'), {
            'nombre': 'Freedom', 'imagen': imagen,
        })

        self.assertRedirects(respuesta, reverse('inicioVariedad'))
        variedad = Variedad.objects.get(nombre='FREEDOM')
        self.assertRegex(variedad.imagen.name, r'^variedades/imagenes/[0-9a-f]{32}\.png$')
        listado = self.client.get(reverse('inicioVariedad'))
        self.assertContains(listado, reverse('imagenVariedad', args=[variedad.pk]))
        imagen_respuesta = self.client.get(reverse('imagenVariedad', args=[variedad.pk]))
        self.assertEqual(imagen_respuesta.status_code, 200)
        self.assertEqual(imagen_respuesta['Content-Type'], 'image/png')
        imagen_respuesta.close()


class FechaDocumentoPersonalTests(TestCase):
    def setUp(self):
        self.directorio_media = TemporaryDirectory()
        self.configuracion_media = override_settings(MEDIA_ROOT=self.directorio_media.name)
        self.configuracion_media.enable()
        usuario = get_user_model().objects.create_superuser(
            username='admin_documento_fecha', password='ClaveDocumento123!'
        )
        finca = Finca.objects.create(
            codigo_finca='FINDOC', nombre='FINCA DOCUMENTOS', ubicacion='CAYAMBE'
        )
        self.personal = Personal.objects.create(
            codigo_personal='PERDOC', nombres='ELENA', apellidos='ROSAS VEGA',
            cedula='1710034065', telefono='0999999999', fecha_ingreso=date(2020, 1, 1),
            area='POSTCOSECHA', finca=finca,
        )
        self.client.force_login(usuario)

    def tearDown(self):
        self.configuracion_media.disable()
        self.directorio_media.cleanup()

    def test_fecha_documento_se_genera_en_servidor(self):
        archivo = SimpleUploadedFile(
            'contrato.pdf', b'%PDF-1.7\ncontenido', content_type='application/pdf'
        )
        respuesta = self.client.post(
            reverse('guardarDocumentoPersonal', args=[self.personal.pk]),
            {
                'nombre': 'Contrato de trabajo', 'archivo': archivo,
                'fecha_documento': '2000-01-01',
            },
        )

        self.assertRedirects(respuesta, reverse('expedientePersonal', args=[self.personal.pk]))
        documento = DocumentoPersonal.objects.get(personal=self.personal)
        self.assertEqual(documento.fecha_documento, timezone.localdate())
        expediente = self.client.get(reverse('expedientePersonal', args=[self.personal.pk]))
        self.assertNotContains(expediente, 'name="fecha_documento"')


class FechasPermisoPersonalTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_superuser(
            username='admin_permiso_fecha', password='ClavePermiso123!'
        )
        finca = Finca.objects.create(
            codigo_finca='FINPER', nombre='FINCA PERMISOS', ubicacion='CAYAMBE'
        )
        self.personal = Personal.objects.create(
            codigo_personal='PERPER', nombres='MARTA', apellidos='FLORES VEGA',
            cedula='1710034065', telefono='0999999999', fecha_ingreso=date(2020, 1, 1),
            area='POSTCOSECHA', finca=finca,
        )
        self.client.force_login(usuario)

    def registrar_permiso(self, desde, hasta, salida='', retorno=''):
        return self.client.post(
            reverse('guardarPermisoPersonal', args=[self.personal.pk]),
            {
                'motivo': 'ASUNTOS_PARTICULARES',
                'observacion': 'Prueba de permiso',
                'fecha_desde': desde.isoformat(),
                'fecha_hasta': hasta.isoformat(),
                'hora_salida': salida,
                'hora_retorno': retorno,
            },
            follow=True,
        )

    def test_rechaza_fecha_anterior_a_hoy_desde_el_servidor(self):
        ayer = timezone.localdate() - timedelta(days=1)

        respuesta = self.registrar_permiso(ayer, timezone.localdate())

        self.assertContains(respuesta, 'La ausencia no puede registrarse en una fecha anterior a hoy')
        self.assertFalse(PermisoPersonal.objects.exists())

    def test_permiso_de_medio_dia_descuenta_solo_las_horas(self):
        hoy = timezone.localdate()

        self.registrar_permiso(hoy, hoy, '12:00', '16:00')

        permiso = PermisoPersonal.objects.get()
        self.assertEqual(permiso.dias_descontados, Decimal('0.50'))
        self.assertEqual(permiso.descuento_legible, '4 horas')

    def test_salida_al_mediodia_y_retorno_manana_descuenta_medio_dia(self):
        hoy = timezone.localdate()

        self.registrar_permiso(hoy, hoy + timedelta(days=1), '12:00', '08:00')

        permiso = PermisoPersonal.objects.get()
        self.assertEqual(permiso.dias_descontados, Decimal('0.50'))
        self.assertEqual(permiso.descuento_legible, '4 horas')

    def test_permiso_de_dos_horas_se_muestra_en_horas(self):
        hoy = timezone.localdate()

        respuesta = self.registrar_permiso(hoy, hoy, '11:40', '13:40')

        permiso = PermisoPersonal.objects.get()
        self.assertEqual(permiso.dias_descontados, Decimal('0.25'))
        self.assertEqual(permiso.descuento_legible, '2 horas')
        self.assertContains(respuesta, 'Se descontaron 2 horas de vacaciones')

    def test_formulario_limita_calendario_desde_hoy(self):
        respuesta = self.client.get(reverse('expedientePersonal', args=[self.personal.pk]))

        self.assertEqual(respuesta.context['fecha_actual'], timezone.localdate().isoformat())
        self.assertContains(respuesta, "desde.min = hoy")
        self.assertContains(respuesta, "hasta.min = hoy")
