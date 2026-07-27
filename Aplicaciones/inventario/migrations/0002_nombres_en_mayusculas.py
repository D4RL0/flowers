from django.db import migrations


def convertir_nombres_a_mayusculas(apps, schema_editor):
    configuracion = (
        ('ProveedorInsumo', ('nombre_contacto', 'nombre_empresa')),
        ('Categoria', ('nombre',)),
        ('UnidadMedida', ('nombre', 'abreviatura')),
        ('Producto', ('nombre', 'marca')),
    )
    for nombre_modelo, campos in configuracion:
        modelo = apps.get_model('inventario', nombre_modelo)
        for registro in modelo.objects.all().iterator():
            for campo in campos:
                valor = getattr(registro, campo, '')
                setattr(registro, campo, valor.strip().upper())
            registro.save(update_fields=campos)


class Migration(migrations.Migration):
    dependencies = [
        ('inventario', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(convertir_nombres_a_mayusculas, migrations.RunPython.noop),
    ]
