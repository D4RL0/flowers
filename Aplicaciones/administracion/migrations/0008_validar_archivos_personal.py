from django.db import migrations, models
import FlorLY.file_security


class Migration(migrations.Migration):
    dependencies = [('administracion', '0007_validar_telefonos_ecuatorianos')]

    operations = [
        migrations.AlterField(
            model_name='documentopersonal',
            name='archivo',
            field=models.FileField(
                upload_to='personal/documentos/',
                validators=[FlorLY.file_security.validate_document],
            ),
        ),
    ]
