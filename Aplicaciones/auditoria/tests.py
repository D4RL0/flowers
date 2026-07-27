from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase

from Aplicaciones.auditoria.models import Bitacora
from FlorLY.audit_helpers import safe_request_data


class AuditoriaSeguridadTests(TestCase):
    def test_oculta_password_y_archivo(self):
        request = RequestFactory().post('/prueba/', {
            'username': 'usuario', 'password': 'NoDebeGuardarse123!',
        })
        request.FILES['archivo'] = SimpleUploadedFile('documento.pdf', b'%PDF-contenido')
        datos = safe_request_data(request)
        self.assertEqual(datos['password'], '[PROTEGIDO]')
        self.assertEqual(datos['archivo']['archivo'], '[PROTEGIDO]')

    def test_registra_acceso_denegado(self):
        usuario = get_user_model().objects.create_user(username='empleado_prueba', password='ClaveSegura123!')
        usuario.groups.add(Group.objects.get(name='Empleado'))
        self.client.force_login(usuario)
        respuesta = self.client.get('/categorias/')
        self.assertEqual(respuesta.status_code, 403)
        evento = Bitacora.objects.get(usuario=usuario)
        self.assertEqual(evento.accion, 'ACCESO DENEGADO')
        self.assertEqual(evento.resultado, 'RECHAZADA')
