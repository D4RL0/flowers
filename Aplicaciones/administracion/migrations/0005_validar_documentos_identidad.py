from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [('administracion', '0004_roles_sistema')]

    operations = [
        migrations.AlterField(
            model_name='personal',
            name='cedula',
            field=models.CharField(
                max_length=10,
                unique=True,
                validators=[django.core.validators.RegexValidator(
                    '^\\d{10}$',
                    'La cédula debe contener exactamente 10 dígitos.',
                )],
            ),
        ),
        migrations.AlterField(
            model_name='proveedor',
            name='cedula_ruc',
            field=models.CharField(
                max_length=13,
                unique=True,
                validators=[django.core.validators.RegexValidator(
                    '^(?:\\d{10}|\\d{13})$',
                    'Ingrese una cédula de 10 dígitos o un RUC de 13 dígitos.',
                )],
            ),
        ),
    ]
