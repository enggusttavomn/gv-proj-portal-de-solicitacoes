from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0004_alter_solicitacao_solicitado_em"),
    ]

    operations = [
        migrations.AlterField(
            model_name="solicitacao",
            name="evento_sap",
            field=models.CharField(max_length=120, blank=True),
        ),
    ]
