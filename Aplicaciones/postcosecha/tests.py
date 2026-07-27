from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from Aplicaciones.administracion.models import Proveedor, Variedad
from Aplicaciones.postcosecha.models import Clasificacion, DetalleClasificacion, DetalleRecepcion, Recepcion
from Aplicaciones.postcosecha.views import _fecha_clasificacion_valida, _horario_recepcion_valido


class HorarioRecepcionTests(SimpleTestCase):
    def test_lunes_a_las_ocho_es_valido(self):
        self.assertTrue(_horario_recepcion_valido(datetime(2026, 7, 20, 8, 0)))

    def test_viernes_despues_de_las_quince_no_es_valido(self):
        self.assertFalse(_horario_recepcion_valido(datetime(2026, 7, 24, 15, 0, 1)))

    def test_sabado_al_mediodia_es_valido(self):
        self.assertTrue(_horario_recepcion_valido(datetime(2026, 7, 25, 12, 0)))

    def test_sabado_despues_del_mediodia_no_es_valido(self):
        self.assertFalse(_horario_recepcion_valido(datetime(2026, 7, 25, 12, 0, 1)))

    def test_domingo_no_es_valido(self):
        self.assertFalse(_horario_recepcion_valido(datetime(2026, 7, 26, 10, 0)))


class FechaClasificacionTests(SimpleTestCase):
    def setUp(self):
        self.hoy = datetime(2026, 7, 26).date()

    def test_hoy_es_valido_para_recepcion_de_hoy(self):
        self.assertTrue(_fecha_clasificacion_valida(self.hoy, self.hoy, self.hoy))

    def test_dos_dias_despues_es_valido(self):
        fecha = self.hoy + timedelta(days=2)
        self.assertTrue(_fecha_clasificacion_valida(fecha, self.hoy, self.hoy))

    def test_fecha_anterior_a_hoy_no_es_valida(self):
        self.assertFalse(_fecha_clasificacion_valida(self.hoy - timedelta(days=1), self.hoy, self.hoy))

    def test_mas_de_dos_dias_no_es_valido(self):
        fecha = self.hoy + timedelta(days=3)
        self.assertFalse(_fecha_clasificacion_valida(fecha, self.hoy, self.hoy))

    def test_no_supera_plazo_de_recepcion_anterior(self):
        recepcion = self.hoy - timedelta(days=2)
        self.assertFalse(_fecha_clasificacion_valida(self.hoy + timedelta(days=1), self.hoy, recepcion))


class ConteoRealClasificacionTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_superuser(
            username='admin_clasificacion', password='ClavePrueba123!', email='prueba@example.com'
        )
        self.client.force_login(usuario)
        proveedor = Proveedor.objects.create(
            codigo_proveedor='PRTEST01', nombres='PROVEEDOR', apellidos='PRUEBA',
            cedula_ruc='1710034065', telefono='0991234567',
        )
        variedad = Variedad.objects.create(codigo_variedad='VATEST01', nombre='FREEDOM')
        recepcion = Recepcion.objects.create(
            codigo_recepcion='RECTEST01', numero_recepcion=900001,
            proveedor=proveedor, fecha_recepcion=timezone.now(),
        )
        self.detalle = DetalleRecepcion.objects.create(
            recepcion=recepcion, variedad=variedad,
            cantidad_mallas=40, tallos_por_malla=30,
        )

    def _clasificar(self, optimos, estandar, nacionales, sobrantes):
        return self.client.post(reverse('guardarClasificacion'), {
            'detalle_recepcion': [str(self.detalle.pk)],
            'cantidad_mallas_procesadas': ['40'],
            'tallos_exportables_optimos': [str(optimos)],
            'tallos_exportables_estandar': [str(estandar)],
            'tallos_nacionales': [str(nacionales)],
            'tallos_sobrantes': [str(sobrantes)],
            'observacion_detalle': ['Conteo real de prueba'],
            'fecha_clasificacion': timezone.localdate().isoformat(),
        })

    def test_guarda_conteo_menor_y_calcula_faltantes_en_reporte(self):
        respuesta = self._clasificar(5, 5, 5, 0)
        self.assertEqual(respuesta.status_code, 302)
        clasificacion = Clasificacion.objects.get(recepcion=self.detalle.recepcion)
        self.assertEqual(DetalleClasificacion.objects.filter(clasificacion=clasificacion).count(), 2)

        reporte = self.client.get(reverse('reporteClasificacion', args=[clasificacion.pk]))
        fila = reporte.context['reportes'][0]['filas'][0]
        self.assertEqual(fila['tallos_recibidos'], 1200)
        self.assertEqual(fila['tallos_contabilizados'], 15)
        self.assertEqual(fila['faltantes'], 1185)

    def test_guarda_sobrantes_sin_cambiar_tallos_exportables(self):
        respuesta = self._clasificar(500, 500, 200, 20)
        self.assertEqual(respuesta.status_code, 302)
        clasificacion = Clasificacion.objects.get(recepcion=self.detalle.recepcion)
        reporte = self.client.get(reverse('reporteClasificacion', args=[clasificacion.pk]))
        fila = reporte.context['reportes'][0]['filas'][0]
        self.assertEqual(fila['total_exportables'], 1000)
        self.assertEqual(fila['tallos_contabilizados'], 1220)
        self.assertEqual(fila['sobrantes_clasificacion'], 20)
        self.assertEqual(fila['faltantes'], 0)

    def test_rechaza_clasificados_mayores_a_los_declarados(self):
        respuesta = self._clasificar(1000, 1000, 1000, 0)
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Clasificacion.objects.filter(recepcion=self.detalle.recepcion).exists())
        self.assertEqual(DetalleClasificacion.objects.filter(detalle_recepcion=self.detalle).count(), 0)

    def test_rechaza_una_variedad_con_todas_las_cantidades_en_cero(self):
        respuesta = self._clasificar(0, 0, 0, 0)
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Clasificacion.objects.filter(recepcion=self.detalle.recepcion).exists())
        self.assertEqual(DetalleClasificacion.objects.filter(detalle_recepcion=self.detalle).count(), 0)
