"""
Script de seed que popula o portal com solicitacoes de exemplo para os dashboards.

Cria 10 solicitacoes completas (2 por status: pendente, aprovacao, retrabalho,
aprovado e cancelado), distribuindo entre projetistas cadastrados.

Uso:
    .venv\\Scripts\\python seed_solicitacoes.py
"""

import os
from datetime import timedelta

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

from portal.models import Prioridade, Solicitacao, SolicitacaoStatus

User = get_user_model()
DEFAULT_PASSWORD = "123"
SAMPLE_PREFIX = "[Seed]"


def ensure_user(username, first_name, last_name, email, group):
    """
    Garante que o usuário exista e esteja associado ao grupo informado.

    Se o usuário já existir, apenas atualiza os dados relevantes e reforça
    a associação ao grupo.
    """
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "email": email or "",
            "is_active": True,
        },
    )
    if created:
        user.set_password(DEFAULT_PASSWORD)
    if email:
        user.email = email
    if first_name:
        user.first_name = first_name
    if last_name:
        user.last_name = last_name
    user.is_active = True
    user.groups.add(group)
    user.save()
    return user


def collect_users_for_group(group_name, fallback_username, fallback_first, fallback_last, fallback_email):
    group, _ = Group.objects.get_or_create(name=group_name)
    users = list(group.user_set.all().order_by("username"))
    if not users:
        # Cria um usuário fallback para garantir o seed mesmo sem usuários reais
        users = [ensure_user(fallback_username, fallback_first, fallback_last, fallback_email, group)]
    return users, group


def make_status_samples():
    solicitantes, _ = collect_users_for_group(
        "SOLICITANTE", "seed.solicitante", "Seed", "Solicitante", "seed.solicitante@example.com"
    )
    projetistas, _ = collect_users_for_group(
        "PROJETISTA", "seed.projetista", "Seed", "Projetista", "seed.projetista@example.com"
    )

    previous = Solicitacao.objects.filter(titulo__startswith=f"{SAMPLE_PREFIX} ")
    removed = previous.count()
    previous.delete()

    prioridade_cycle = [
        Prioridade.MEDIA,
        Prioridade.ALTA,
        Prioridade.BAIXA,
        Prioridade.CRITICA,
    ]
    tipo_cycle = ["PD", "Projeto", "Qualidade", "Processo", "R&D"]
    linha_cycle = ["Linha Alpha", "Linha Beta", "Linha Gama", "Linha Delta"]

    created = []
    base_dt = timezone.localtime(timezone.now()).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    cases = [
        ("Pendente", SolicitacaoStatus.EM_FILA),
        ("Pendente", SolicitacaoStatus.EM_PROJETO),
        ("Aprovacao", SolicitacaoStatus.AGUARDANDO_APROVACAO),
        ("Aprovacao", SolicitacaoStatus.AGUARDANDO_APROVACAO),
        ("Retrabalho", SolicitacaoStatus.RETRABALHO),
        ("Retrabalho", SolicitacaoStatus.RETRABALHO),
        ("Aprovado", SolicitacaoStatus.APROVADO),
        ("Aprovado", SolicitacaoStatus.APROVADO),
        ("Cancelado", SolicitacaoStatus.CANCELADO),
        ("Cancelado", SolicitacaoStatus.CANCELADO),
    ]

    solicitante_fixo = next(
        (user for user in solicitantes if (user.first_name or "").strip().lower() == "danilo"),
        None,
    ) or solicitantes[0]

    for idx, (label, target_status) in enumerate(cases, start=1):
        prioridade = prioridade_cycle[(idx - 1) % len(prioridade_cycle)]
        tipo = tipo_cycle[(idx - 1) % len(tipo_cycle)]
        linha = linha_cycle[(idx - 1) % len(linha_cycle)]
        solicitante = solicitante_fixo
        projetista = projetistas[(idx - 1) % len(projetistas)]
        solicitado_at = base_dt - timedelta(days=idx * 3)
        prazo_estimado = solicitado_at.date() + timedelta(days=30 + idx)
        baseline_ame = solicitado_at.date() + timedelta(days=10 + idx)
        baseline_producao = solicitado_at.date() + timedelta(days=20 + idx)

        number_stamp = f"{idx:02d}"
        job = f"GV-TEST-{number_stamp}"
        title = f"{SAMPLE_PREFIX} Status {number_stamp} - {label}"
        sufixo = f"{idx:04d}"
        solic = Solicitacao.objects.create(
            titulo=title,
            descricao=f"Solicitacao de teste {label.lower()} {number_stamp}.",
            secao=f"Secao {label}",
            job=job,
            jobs_envolvidas="ENG;FAB;SUP",
            sufixo=sufixo,
            descricao_ferramenta=f"Ferramenta {job}",
            desenho_referencia=f"REF-{job}",
            wc=f"WC-{idx:02d}",
            quantidade=max(1, (idx % 5) + 1),
            solicitado_em=solicitado_at,
            evento_sap=f"Evento {label} {number_stamp}",
            numero_moc=f"MOC-{number_stamp}",
            numero_dispositivo=f"DISP-{number_stamp}",
            area=f"Area {label}",
            tipo_identificacao=tipo,
            linha_produto=linha,
            descricao_tecnica=f"Descricao tecnica para {label.lower()}",
            material="ACO 1020",
            tratamento="PINTURA ELETROSTATICA",
            dim_criticas=f"Diam {10 + idx * 0.5:.2f} +/- 0.10 mm",
            observacoes_projeto="Verificar tolerancias e liberar kit.",
            observacoes_aprovacao="Aguardar aprovacao final do solicitante.",
            prazo_estimado=prazo_estimado,
            baseline_ame=baseline_ame,
            baseline_producao=baseline_producao,
            status=SolicitacaoStatus.EM_FILA,
            prioridade=prioridade,
            criado_por=solicitante,
            atribuido_para=projetista,
        )

        if target_status == SolicitacaoStatus.EM_PROJETO:
            solic.mudar_status(
                SolicitacaoStatus.EM_PROJETO,
                projetista,
                comentario="Inicio de projeto.",
            )
        elif target_status == SolicitacaoStatus.AGUARDANDO_APROVACAO:
            for status, user, comentario in [
                (SolicitacaoStatus.EM_PROJETO, projetista, "Inicio de projeto."),
                (
                    SolicitacaoStatus.AGUARDANDO_APROVACAO,
                    projetista,
                    "Projeto pronto para aprovacao.",
                ),
            ]:
                solic.mudar_status(status, user, comentario=comentario)
        elif target_status == SolicitacaoStatus.RETRABALHO:
            for status, user, comentario in [
                (SolicitacaoStatus.EM_PROJETO, projetista, "Inicio de projeto."),
                (
                    SolicitacaoStatus.AGUARDANDO_APROVACAO,
                    projetista,
                    "Projeto pronto para aprovacao.",
                ),
                (
                    SolicitacaoStatus.RETRABALHO,
                    solicitante,
                    "Retrabalho solicitado: ajustar dimensoes.",
                ),
            ]:
                solic.mudar_status(status, user, comentario=comentario)
        elif target_status == SolicitacaoStatus.APROVADO:
            for status, user, comentario in [
                (SolicitacaoStatus.EM_PROJETO, projetista, "Inicio de projeto."),
                (
                    SolicitacaoStatus.AGUARDANDO_APROVACAO,
                    projetista,
                    "Projeto pronto para aprovacao.",
                ),
                (
                    SolicitacaoStatus.APROVADO,
                    solicitante,
                    "Aprovado para fabricacao.",
                ),
            ]:
                solic.mudar_status(status, user, comentario=comentario)
        elif target_status == SolicitacaoStatus.CANCELADO:
            for status, user, comentario in [
                (SolicitacaoStatus.EM_PROJETO, projetista, "Inicio de projeto."),
                (
                    SolicitacaoStatus.AGUARDANDO_APROVACAO,
                    projetista,
                    "Projeto pronto para aprovacao.",
                ),
                (
                    SolicitacaoStatus.CANCELADO,
                    solicitante,
                    "Cancelado pelo solicitante.",
                ),
            ]:
                solic.mudar_status(status, user, comentario=comentario)

        created.append(solic)

    print(f"Removidas {removed} solicitacoes de amostra anteriores.")
    print(f"Criadas {len(created)} solicitacoes de amostra com status variados.")


if __name__ == "__main__":
    make_status_samples()
