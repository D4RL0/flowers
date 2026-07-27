from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from FlorLY.file_security import MAX_DOCUMENT_SIZE, validate_and_secure_document
from FlorLY.security import (
    clear_login_failures, login_is_blocked, register_login_failure,
)


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
