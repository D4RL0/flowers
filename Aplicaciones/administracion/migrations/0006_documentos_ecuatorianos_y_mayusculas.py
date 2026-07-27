from django.db import migrations, models

import Aplicaciones.administracion.validators


def convertir_nombres_a_mayusculas(apps, schema_editor):
    for nombre_modelo, campos in (
        ('Proveedor', ('nombres', 'apellidos')),
        ('Personal', ('nombres', 'apellidos')),
        ('Variedad', ('nombre',)),
        ('Finca', ('nombre',)),
    ):
        modelo = apps.get_model('administracion', nombre_modelo)
        for registro in modelo.objects.all().iterator():
            for campo in campos:
                valor = getattr(registro, campo, '')
                setattr(registro, campo, valor.strip().upper())
            registro.save(update_fields=campos)


class Migration(migrations.Migration):
    dependencies = [
        ('administracion', '0005_validar_documentos_identidad'),
    ]

    operations = [
        migrations.AlterField(
            model_name='personal',
            name='cedula',
            field=models.CharField(
                max_length=10,
                unique=True,
                validators=[Aplicaciones.administracion.validators.validar_cedula_ecuatoriana],
            ),
        ),
        migrations.AlterField(
            model_name='proveedor',
            name='cedula_ruc',
            field=models.CharField(
                max_length=13,
                unique=True,
                validators=[Aplicaciones.administracion.validators.validar_documento_ecuatoriano],
            ),
        ),
        migrations.RunPython(convertir_nombres_a_mayusculas, migrations.RunPython.noop),
    ]
