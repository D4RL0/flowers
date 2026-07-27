from django.db import migrations, models


def actualizar_estados(apps, schema_editor):
    Liquidacion = apps.get_model('liquidaciones', 'Liquidacion')
    Liquidacion.objects.filter(estado='PENDIENTE').update(estado='PEND_DOCUMENTO')


class Migration(migrations.Migration):
    dependencies = [
        ('liquidaciones', '0001_initial'),
        ('postcosecha', '0004_clasificacion_por_recepcion'),
    ]

    operations = [
        migrations.AlterField(
            model_name='liquidacion',
            name='estado',
            field=models.CharField(
                choices=[
                    ('PEND_DOCUMENTO', 'Pendiente de documento'),
                    ('PEND_PAGO', 'Pendiente de pago'),
                    ('PAGADA', 'Pagada'),
                ],
                default='PEND_DOCUMENTO',
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name='liquidacion',
            name='clasificaciones',
            field=models.ManyToManyField(
                blank=True,
                related_name='liquidaciones',
                to='postcosecha.clasificacion',
            ),
        ),
        migrations.RunPython(actualizar_estados, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='liquidacion',
            constraint=models.UniqueConstraint(
                fields=('proveedor', 'fecha_liquidacion'),
                name='liq_unica_proveedor_fecha_cierre',
            ),
        ),
    ]
