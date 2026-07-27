from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('postcosecha', '0001_initial')]

    operations = [
        migrations.AddField(
            model_name='detallerecepcion',
            name='tallos_por_malla',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
