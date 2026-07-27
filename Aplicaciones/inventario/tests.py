import json

from django.test import RequestFactory, TestCase

from Aplicaciones.inventario.models import UnidadMedida
from Aplicaciones.inventario.views import guardarUnidadMedidaRapida


class UnidadMedidaRapidaTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_crea_unidad_en_mayusculas(self):
        request = self.factory.post('/unidades-medida/guardar-rapida/', {
            'nombre': 'libra', 'abreviatura': 'lb',
        })
        respuesta = guardarUnidadMedidaRapida(request)
        self.assertEqual(respuesta.status_code, 200)
        unidad = UnidadMedida.objects.get()
        self.assertEqual((unidad.nombre, unidad.abreviatura), ('LIBRA', 'LB'))

    def test_rechaza_abreviatura_repetida_sin_importar_mayusculas(self):
        UnidadMedida.objects.create(
            codigo_unidad_medida='UM0001', nombre='LIBRA', abreviatura='LB'
        )
        request = self.factory.post('/unidades-medida/guardar-rapida/', {
            'nombre': 'OTRA', 'abreviatura': 'lb',
        })
        respuesta = guardarUnidadMedidaRapida(request)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('abreviatura', json.loads(respuesta.content)['error'])
