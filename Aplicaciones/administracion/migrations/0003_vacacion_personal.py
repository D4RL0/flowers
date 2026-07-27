from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('administracion', '0002_permisos_documentos_personal')]

    operations = [
        migrations.CreateModel(
            name='VacacionPersonal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_desde', models.DateField()),
                ('fecha_hasta', models.DateField()),
                ('dias_tomados', models.PositiveIntegerField()),
                ('observacion', models.TextField(blank=True)),
                ('fecha_registro', models.DateTimeField(auto_now_add=True)),
                ('personal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vacaciones', to='administracion.personal')),
            ],
        ),
    ]
