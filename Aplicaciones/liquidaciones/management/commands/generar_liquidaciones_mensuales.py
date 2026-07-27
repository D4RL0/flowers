from django.core.management.base import BaseCommand
from django.utils import timezone

from Aplicaciones.liquidaciones.services import generar_liquidaciones_vencidas


class Command(BaseCommand):
    help = 'Genera las liquidaciones mensuales vencidas sin duplicar clasificaciones.'

    def handle(self, *args, **options):
        generadas, errores = generar_liquidaciones_vencidas(timezone.localdate())
        for liquidacion in generadas:
            self.stdout.write(self.style.SUCCESS(
                f'{liquidacion.codigo_liquidacion}: {liquidacion.proveedor}'
            ))
        for error in errores:
            self.stderr.write(self.style.ERROR(error))
        self.stdout.write(f'Liquidaciones generadas: {len(generadas)}')
