from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0007_dispositivo_catalogo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitacao",
            name="aprovado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="aprovado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitacoes_aprovadas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="aprovado_comentario",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="reprovado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="reprovado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitacoes_reprovadas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="reprovado_comentario",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="retrabalho_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="retrabalho_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitacoes_retrabalho",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="retrabalho_comentario",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="cancelado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="cancelado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitacoes_canceladas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="cancelado_comentario",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="concluido_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="concluido_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitacoes_concluidas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="solicitacao",
            name="concluido_comentario",
            field=models.TextField(blank=True),
        ),
    ]
