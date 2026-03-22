from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0006_alter_solicitacao_desenho_referencia"),
    ]

    operations = [
        migrations.CreateModel(
            name="DispositivoCatalogo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=40, unique=True)),
                ("descricao", models.TextField()),
            ],
            options={
                "ordering": ["codigo"],
            },
        ),
    ]
