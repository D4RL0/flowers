from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('auditoria', '0001_initial')]

    operations = [
        migrations.AddField(model_name='bitacora', name='metodo', field=models.CharField(blank=True, max_length=10)),
        migrations.AddField(model_name='bitacora', name='ruta', field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name='bitacora', name='resultado', field=models.CharField(default='REGISTRADA', max_length=20)),
        migrations.AddField(model_name='bitacora', name='datos_anteriores', field=models.JSONField(blank=True, null=True)),
        migrations.AddField(model_name='bitacora', name='datos_nuevos', field=models.JSONField(blank=True, null=True)),
    ]
