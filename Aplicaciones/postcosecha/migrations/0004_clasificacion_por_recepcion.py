import django.db.models.deletion
from django.db import migrations, models


def relacionar_clasificaciones_existentes(apps, schema_editor):
    Clasificacion = apps.get_model('postcosecha', 'Clasificacion')
    recepciones_asignadas = set()
    for clasificacion in Clasificacion.objects.all().order_by('codigo_clasificacion'):
        recepciones = list(clasificacion.detalleclasificacion_set.values_list(
            'detalle_recepcion__recepcion_id', flat=True
        ).distinct()[:2])
        if len(recepciones) == 1 and recepciones[0] not in recepciones_asignadas:
            clasificacion.recepcion_id = recepciones[0]
            clasificacion.save(update_fields=['recepcion'])
            recepciones_asignadas.add(recepciones[0])


class Migration(migrations.Migration):
    dependencies = [('postcosecha', '0003_mover_encargado_a_recepcion')]

    operations = [
        migrations.AddField(
            model_name='clasificacion',
            name='recepcion',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='clasificacion',
                to='postcosecha.recepcion',
            ),
        ),
        migrations.RunPython(relacionar_clasificaciones_existentes, migrations.RunPython.noop),
    ]
