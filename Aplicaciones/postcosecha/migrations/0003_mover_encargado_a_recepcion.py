import django.db.models.deletion
from django.db import migrations, models


def conservar_encargados_existentes(apps, schema_editor):
    Clasificacion = apps.get_model('postcosecha', 'Clasificacion')
    for clasificacion in Clasificacion.objects.exclude(encargado_id=None):
        recepcion_ids = clasificacion.detalleclasificacion_set.values_list(
            'detalle_recepcion__recepcion_id', flat=True
        ).distinct()
        apps.get_model('postcosecha', 'Recepcion').objects.filter(
            pk__in=recepcion_ids, empleado_receptor_id=None
        ).update(empleado_receptor_id=clasificacion.encargado_id)


class Migration(migrations.Migration):
    dependencies = [('postcosecha', '0002_detallerecepcion_tallos_por_malla')]

    operations = [
        migrations.AddField(
            model_name='recepcion',
            name='empleado_receptor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='recepciones_realizadas',
                to='administracion.personal',
            ),
        ),
        migrations.RunPython(conservar_encargados_existentes, migrations.RunPython.noop),
        migrations.RemoveField(model_name='clasificacion', name='encargado'),
    ]
