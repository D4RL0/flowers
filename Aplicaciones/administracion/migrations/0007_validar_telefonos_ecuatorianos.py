from django.db import migrations, models

import Aplicaciones.administracion.validators


class Migration(migrations.Migration):
    dependencies = [
        ('administracion', '0006_documentos_ecuatorianos_y_mayusculas'),
    ]

    operations = [
        migrations.AlterField(
            model_name='personal',
            name='telefono',
            field=models.CharField(
                max_length=15,
                validators=[Aplicaciones.administracion.validators.validar_telefono_ecuatoriano],
            ),
        ),
        migrations.AlterField(
            model_name='proveedor',
            name='telefono',
            field=models.CharField(
                max_length=15,
                validators=[Aplicaciones.administracion.validators.validar_telefono_ecuatoriano],
            ),
        ),
    ]
