from datetime import date

from django.test import SimpleTestCase

from Aplicaciones.liquidaciones.services import fechas_ciclos_vencidos


class FechasCicloLiquidacionTests(SimpleTestCase):
    def test_ejemplo_proveedor_27_julio(self):
        ciclos = fechas_ciclos_vencidos(date(2026, 7, 27), date(2026, 8, 26))
        self.assertEqual(ciclos, [(date(2026, 8, 26), date(2026, 8, 24))])

    def test_no_cierra_antes_de_la_fecha(self):
        ciclos = fechas_ciclos_vencidos(date(2026, 7, 27), date(2026, 8, 25))
        self.assertEqual(ciclos, [])

    def test_ajusta_fin_de_mes(self):
        ciclos = fechas_ciclos_vencidos(date(2026, 1, 31), date(2026, 2, 27))
        self.assertEqual(ciclos, [(date(2026, 2, 27), date(2026, 2, 25))])
