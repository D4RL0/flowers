from django.db import migrations


def crear_roles(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for nombre in ('Administrador', 'Secretaria', 'Empleado'):
        Group.objects.get_or_create(name=nombre)


class Migration(migrations.Migration):
    dependencies = [
        ('administracion', '0003_vacacion_personal'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [migrations.RunPython(crear_roles, migrations.RunPython.noop)]
