from django.db import migrations, models

import Aplicaciones.administracion.validators


class Migration(migrations.Migration):
    dependencies = [
        ('inventario', '0002_nombres_en_mayusculas'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proveedorinsumo',
            name='telefono',
            field=models.CharField(
                max_length=15,
                validators=[Aplicaciones.administracion.validators.validar_telefono_ecuatoriano],
            ),
        ),
    ]
