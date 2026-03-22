from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0008_add_solicitacao_workflow_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("acao", models.CharField(db_index=True, max_length=80)),
                ("descricao", models.TextField(blank=True)),
                ("grupo", models.CharField(blank=True, max_length=40)),
                ("entidade", models.CharField(blank=True, max_length=80)),
                ("entidade_id", models.PositiveIntegerField(blank=True, null=True)),
                ("dados", models.JSONField(blank=True, null=True)),
                ("ip", models.CharField(blank=True, max_length=45)),
                ("user_agent", models.CharField(blank=True, max_length=256)),
                ("path", models.CharField(blank=True, max_length=200)),
                ("method", models.CharField(blank=True, max_length=10)),
                ("criado_em", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("solicitacao", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_logs", to="portal.solicitacao")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="audit_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-criado_em"],
            },
        ),
    ]
