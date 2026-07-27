from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('administracion', '0001_initial')]

    operations = [
        migrations.CreateModel(
            name='PermisoPersonal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('motivo', models.CharField(choices=[('CITA_MEDICA', 'Cita médica'), ('CALAMIDAD_DOMESTICA', 'Calamidad doméstica'), ('ASUNTOS_PARTICULARES', 'Asuntos particulares'), ('OTRO', 'Otro')], max_length=30)),
                ('observacion', models.TextField(blank=True)),
                ('fecha_desde', models.DateField()),
                ('fecha_hasta', models.DateField()),
                ('hora_salida', models.TimeField(blank=True, null=True)),
                ('hora_retorno', models.TimeField(blank=True, null=True)),
                ('dias_descontados', models.DecimalField(decimal_places=2, max_digits=7)),
                ('fecha_registro', models.DateTimeField(auto_now_add=True)),
                ('personal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permisos', to='administracion.personal')),
            ],
        ),
        migrations.CreateModel(
            name='DocumentoPersonal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=150)),
                ('archivo', models.FileField(upload_to='personal/documentos/')),
                ('observacion', models.TextField(blank=True)),
                ('fecha_documento', models.DateField(default=django.utils.timezone.localdate)),
                ('fecha_registro', models.DateTimeField(auto_now_add=True)),
                ('personal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documentos', to='administracion.personal')),
            ],
        ),
    ]
