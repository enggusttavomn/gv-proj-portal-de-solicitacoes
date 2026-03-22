from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0005_alter_solicitacao_evento_sap_length"),
    ]

    operations = [
        migrations.AlterField(
            model_name="solicitacao",
            name="desenho_referencia",
            field=models.TextField(blank=True),
        ),
    ]
