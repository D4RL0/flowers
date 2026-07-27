from django.db import migrations, models
import FlorLY.file_security


class Migration(migrations.Migration):
    dependencies = [('liquidaciones', '0002_ciclo_automatico')]

    operations = [
        migrations.AlterField(
            model_name='liquidacion',
            name='documento_proveedor',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='liquidaciones/documentos/',
                validators=[FlorLY.file_security.validate_document],
            ),
        ),
    ]
