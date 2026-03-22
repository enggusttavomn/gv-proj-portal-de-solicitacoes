from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0003_add_solicitacao_sufixo_numero_dispositivo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="solicitacao",
            name="solicitado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
