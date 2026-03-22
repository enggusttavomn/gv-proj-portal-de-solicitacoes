"""
Views (Visualizações/Páginas) da app de portal.

Este é o arquivo principal que contém toda a lógica de negócio do sistema FRNR.
Responsável por:

1. **Autenticação e Acesso**: Decoradores para verificar permissões por grupo
2. **Dashboards**: Páginas principais para cada tipo de usuário
   - Admin: gerenciamento geral
   - Solicitante: acompanhamento de solicitações
   - Projetista: lista de tarefas e preenchimento de dados
   - Dispositivos: gerenciamento do catálogo
3. **Fluxo de Solicitações**: Criação, edição, aprovação e rejeição
4. **Funções Auxiliares**: Mapeamento de projetistas, formatação de dados, etc.

Estrutura do arquivo:
- Imports e constantes (mapeamentos)
- Funções auxiliares (_prefixo indica uso interno)
- Decoradores de autenticação
- Views de dashboards
- Views de operações (criar, editar, aprovar, etc.)
- Views de API/JSON
"""

from functools import wraps
import calendar
import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connections, models
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from pathlib import Path

from accounts.models import UserProfile
from accounts.directory import (
    DEFAULT_PASSWORD_PLACEHOLDER,
    USER_DIRECTORY,
    find_directory_entry,
    get_display_profile,
)

from .models import Prioridade, SolicitacaoStatus, Solicitacao, SolicitacaoLog, AuditLog
from .audit import log_action, AUDIT_ACTION_LABELS

# ==============================================================================
# CONSTANTES E MAPEAMENTOS
# ==============================================================================

# Mapeamento de códigos de dispositivos para projetistas responsáveis
# Exemplo: códigos "0321", "0359", etc pertencem a "Marina"
_PROJETISTA_SUFFIX_MAP = {
    "Marina": {
        "0321", "0359", "0107", "1048", "8175", "0102", "0243", "0240", "0742", "0293",
        "0238", "0291", "0292", "8186", "1149", "8062", "1040", "0246", "0101", "1167",
        "0120", "0122", "1038", "0124", "0147", "0125", "8151", "0229", "2113", "0069",
        "0814", "0673", "8099", "0160", "0304", "1195", "0311",
    },
    "Otavio": {
        "0015", "1018", "0947", "8173", "1157", "0012", "0014", "0018", "0019", "0030",
        "0083", "1019", "2011", "0022", "0223", "0217", "0221", "0247", "0010", "0025",
        "0011", "0024", "1011", "2010", "8146", "8166", "0431", "8107", "8187", "0218",
        "0492", "0427",
    },
    "Rafael Moreira": {
        "1161", "0628", "1274", "1002", "8145", "1047", "8033", "8021", "8116", "0435",
        "1273", "1269", "2050", "8119", "8123", "1126", "0938", "0253", "8124", "8184",
        "0237", "0294", "0234",
    },
    "Nicolas Vieira": {
        "0009", "0003", "0004", "0006", "0399", "0561", "8129", "0577", "0544", "0545",
        "0316", "8135", "0318", "8104", "8034", "0692", "0187", "0509", "8127", "8183",
        "0999", "0036", "1229", "0139", "0110", "0290", "0675", "0189", "0714", "8196",
    },
    "Patricia Gomes": {
        "0228", "8019", "0224", "0272", "0239", "0029", "8158", "8136", "0032", "0033",
        "0028", "0034", "0355", "8087", "8106", "8125", "1144", "0288", "0289", "8193",
        "0644", "0854", "8148", "0241",
    },
}

# Projetista padrão para solicitações que não se enquadram em nenhuma categoria
_PROJETISTA_DEFAULT = "Otavio"

# Opções de telas disponíveis por tipo de usuário (usado na navegação)
_ADMIN_SCREEN_OPTIONS = {
    "SOLICITANTE": {
        "dashboard_solicitante": "Dashboard",
        "novo_apontamento": "Criar nova solicitacao",
        "status_do_projeto": "Controle de projetos",
        "aprovar_reaprovar": "Aprovar / Reaprovar",
        "solicitar_retrabalho": "Solicitar retrabalho",
        "retorno_final": "Retorno final",
    },
}

_INLINE_FIELD_CONFIG = [
    {"name": "id", "label": "ID", "type": "number", "editable": False},
    {"name": "status", "label": "Status", "type": "select", "editable": True, "choices_key": "status"},
    {"name": "descricao", "label": "Descrição", "type": "textarea", "editable": True},
    {"name": "secao", "label": "Seção", "type": "text", "editable": True},
    {"name": "area", "label": "Área", "type": "text", "editable": True},
    {"name": "job", "label": "Job", "type": "text", "editable": True},
    {"name": "jobs_envolvidas", "label": "Jobs envolvidas", "type": "text", "editable": True},
    {"name": "sufixo", "label": "Sufixo", "type": "text", "editable": True},
    {"name": "descricao_ferramenta", "label": "Descrição ferramenta", "type": "textarea", "editable": True},
    {"name": "desenho_referencia", "label": "Desenho referencia + PT", "type": "text", "editable": True},
    {"name": "descricao_tecnica", "label": "Descrição técnica", "type": "textarea", "editable": True},
    {"name": "dim_criticas", "label": "Dimensões críticas", "type": "textarea", "editable": True},
    {"name": "observacoes_projeto", "label": "Obs. projeto", "type": "textarea", "editable": True},
    {"name": "observacoes_aprovacao", "label": "Obs. aprovação", "type": "textarea", "editable": True},
    {"name": "aprovado_em", "label": "Aprovado em", "type": "datetime", "editable": False},
    {"name": "aprovado_por", "label": "Aprovado por", "type": "text", "editable": False},
    {"name": "aprovado_comentario", "label": "Comentario aprovacao", "type": "textarea", "editable": False},
    {"name": "reprovado_em", "label": "Reprovado em", "type": "datetime", "editable": False},
    {"name": "reprovado_por", "label": "Reprovado por", "type": "text", "editable": False},
    {"name": "reprovado_comentario", "label": "Comentario reprovacao", "type": "textarea", "editable": False},
    {"name": "retrabalho_em", "label": "Retrabalho em", "type": "datetime", "editable": False},
    {"name": "retrabalho_por", "label": "Retrabalho por", "type": "text", "editable": False},
    {"name": "retrabalho_comentario", "label": "Comentario retrabalho", "type": "textarea", "editable": False},
    {"name": "cancelado_em", "label": "Cancelado em", "type": "datetime", "editable": False},
    {"name": "cancelado_por", "label": "Cancelado por", "type": "text", "editable": False},
    {"name": "cancelado_comentario", "label": "Comentario cancelado", "type": "textarea", "editable": False},
    {"name": "concluido_em", "label": "Concluido em", "type": "datetime", "editable": False},
    {"name": "concluido_por", "label": "Concluido por", "type": "text", "editable": False},
    {"name": "concluido_comentario", "label": "Comentario conclusao", "type": "textarea", "editable": False},
    {"name": "anexos", "label": "Anexos", "type": "text", "editable": False},
    {"name": "wc", "label": "WC", "type": "text", "editable": True},
    {"name": "quantidade", "label": "Quantidade", "type": "number", "editable": True},
    {"name": "evento_sap", "label": "Evento SAP", "type": "text", "editable": True},
    {"name": "numero_moc", "label": "Número MOC", "type": "text", "editable": True},
    {"name": "numero_dispositivo", "label": "Número do disp.", "type": "text", "editable": True},
    {"name": "tipo_identificacao", "label": "Tipo identificação", "type": "text", "editable": True},
    {"name": "linha_produto", "label": "Linha produto", "type": "text", "editable": True},
    {"name": "material", "label": "Material", "type": "text", "editable": True},
    {"name": "tratamento", "label": "Tratamento", "type": "text", "editable": True},
    {"name": "prazo_estimado", "label": "Prazo estimado", "type": "date", "editable": False},
    {"name": "baseline_ame", "label": "Baseline AME", "type": "date", "editable": False},
    {"name": "baseline_producao", "label": "Baseline produção", "type": "date", "editable": False},
    {"name": "solicitado_em", "label": "Solicitado em", "type": "datetime", "editable": False},
    {"name": "criado_por", "label": "Solicitante", "type": "text", "editable": False},
    {"name": "atribuido_para", "label": "Projetista", "type": "text", "editable": False},
    {"name": "criado_em", "label": "Criado em", "type": "datetime", "editable": False},
    {"name": "atualizado_em", "label": "Atualizado em", "type": "datetime", "editable": False},
]
_INLINE_FIELD_MAP = {field["name"]: field for field in _INLINE_FIELD_CONFIG}

# Status cards used in the admin dashboard (mirrors template list)
_STATUS_BAR_ITEMS = [
    ("pendente", "Pendente"),
    ("aprovacao", "Em aprovação"),
    ("retrabalho", "Retrabalho"),
    ("reprovado", "Reprovado"),
    ("aprovado", "Aprovado"),
]

_STATUS_TREND_LINES = [
    {
        "key": "pendente",
        "label": "Pendente",
        "statuses": [SolicitacaoStatus.EM_FILA, SolicitacaoStatus.EM_PROJETO],
        "color": "#0b5f53",
    },
    {
        "key": "aprovacao",
        "label": "Em aprovação",
        "statuses": [SolicitacaoStatus.AGUARDANDO_APROVACAO],
        "color": "#2563eb",
    },
    {
        "key": "retrabalho",
        "label": "Retrabalho",
        "statuses": [SolicitacaoStatus.RETRABALHO],
        "color": "#ca8a04",
    },
    {
        "key": "reprovado",
        "label": "Reprovado",
        "statuses": [SolicitacaoStatus.REPROVADO],
        "color": "#dc2626",
    },
    {
        "key": "aprovado",
        "label": "Aprovado",
        "statuses": [SolicitacaoStatus.APROVADO, SolicitacaoStatus.CONCLUIDO],
        "color": "#0ea5e9",
    },
]

_SOLICITANTE_TREND_LINES = [
    {
        "key": "pendente",
        "label": "Pendente",
        "statuses": [SolicitacaoStatus.EM_FILA, SolicitacaoStatus.EM_PROJETO],
        "color": "rgba(100,116,139,.95)",
        "fill": "rgba(100,116,139,.20)",
    },
    {
        "key": "aprovacao",
        "label": "Em aprovação",
        "statuses": [SolicitacaoStatus.AGUARDANDO_APROVACAO],
        "color": "rgba(59,130,246,.95)",
        "fill": "rgba(59,130,246,.15)",
    },
    {
        "key": "retrabalho",
        "label": "Retrabalho",
        "statuses": [SolicitacaoStatus.RETRABALHO],
        "color": "rgba(245,158,11,.95)",
        "fill": "rgba(245,158,11,.15)",
    },
    {
        "key": "aprovado",
        "label": "Aprovado",
        "statuses": [SolicitacaoStatus.APROVADO, SolicitacaoStatus.CONCLUIDO],
        "color": "rgba(11,95,83,.95)",
        "fill": "rgba(11,95,83,.20)",
    },
    {
        "key": "cancelado",
        "label": "Cancelado",
        "statuses": [SolicitacaoStatus.CANCELADO],
        "color": "rgba(220,38,38,.95)",
        "fill": "rgba(220,38,38,.15)",
    },
]

_PT_WEEKDAY_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
_PT_MONTH_ABBR = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# Mapeamento de status para metadados de apresentação (label, classe CSS, etc)
_STATUS_META = {
    SolicitacaoStatus.RASCUNHO: {
        "key": "rascunho",
        "label": "Em espera",
        "class": "muted",
    },
    SolicitacaoStatus.EM_FILA: {
        "key": "aguardando_projetista",
        "label": "Aguardando retorno do projetista",
        "class": "pending",
    },
    SolicitacaoStatus.EM_PROJETO: {
        "key": "aguardando_projetista",
        "label": "Aguardando retorno do projetista",
        "class": "pending",
    },
    SolicitacaoStatus.AGUARDANDO_APROVACAO: {
        "key": "aguardando_aprovacao",
        "label": "Aguardando aprovacao do solicitante",
        "class": "warning",
    },
    SolicitacaoStatus.RETRABALHO: {
        "key": "aguardando_retrabalho",
        "label": "Aguardando retorno do projetista",
        "class": "rework",
    },
    SolicitacaoStatus.APROVADO: {
        "key": "aprovado",
        "label": "Aprovado",
        "class": "ok",
    },
    SolicitacaoStatus.REPROVADO: {
        "key": "reprovado",
        "label": "Reprovado",
        "class": "danger",
    },
    SolicitacaoStatus.CONCLUIDO: {
        "key": "concluido",
        "label": "Concluido",
        "class": "ok",
    },
    SolicitacaoStatus.CANCELADO: {
        "key": "cancelado",
        "label": "Cancelado",
        "class": "muted",
    },
}

# Opções de filtro disponíveis para o usuário visualizar solicitações por status
_STATUS_FILTER_OPTIONS = [
    ("", "Todos os status", None),
    ("aguardando_projetista", "Aguardando retorno do projetista", [SolicitacaoStatus.EM_FILA, SolicitacaoStatus.EM_PROJETO]),
    ("aguardando_aprovacao", "Aguardando aprovacao do solicitante", [SolicitacaoStatus.AGUARDANDO_APROVACAO]),
    ("aguardando_retrabalho", "Aguardando retorno do projetista", [SolicitacaoStatus.RETRABALHO]),
    ("retorno_final", "Aprovado", [SolicitacaoStatus.APROVADO]),
    ("concluido", "Concluido", [SolicitacaoStatus.CONCLUIDO]),
    ("reprovado", "Reprovado", [SolicitacaoStatus.REPROVADO]),
    ("cancelado", "Cancelado", [SolicitacaoStatus.CANCELADO]),
]

# Mapa rápido para converter filtro em lista de status
_STATUS_FILTER_MAP = {key: statuses for key, _, statuses in _STATUS_FILTER_OPTIONS if key}

# Statuses that allow solicitante actions from the controle page.
_SOLICITANTE_ACTION_ALLOWED_STATUSES = {
    "aprovar": {SolicitacaoStatus.AGUARDANDO_APROVACAO},
    "retrabalho": {SolicitacaoStatus.AGUARDANDO_APROVACAO},
    "cancelar": {SolicitacaoStatus.AGUARDANDO_APROVACAO},
}
_SOLICITANTE_ACTION_STATUS_ERR = (
    "A ação só está disponível quando a solicitação estiver aguardando aprovação do solicitante."
)

# Status finais (não mudam mais de estado)
_FINAL_STATUS_VALUES = {
    SolicitacaoStatus.CONCLUIDO,
    SolicitacaoStatus.REPROVADO,
    SolicitacaoStatus.CANCELADO,
}
_FINAL_STATUS_KEYS = {"concluido", "reprovado", "cancelado"}

# ==============================================================================
# FUNÇÕES AUXILIARES (PREFIXO _)
# ==============================================================================

def _resolve_projetista_nome(sufixo: str) -> str:
    """
    Resolve o nome do projetista responsável baseado no sufixo do dispositivo.
    
    Algoritmo:
    1. Se contém 'R' ou 'G' no sufixo, retorna 'Filipe'
    2. Extrai códigos de 4 dígitos do sufixo
    3. Procura qual projetista tem esses códigos mapeados
    4. Se não encontrar, retorna projetista padrão
    
    Args:
        sufixo: String com sufixo/código do dispositivo (ex: "0321", "RG1048")
        
    Returns:
        str: Nome do projetista (ex: "Marina", "Otavio") ou string vazia
    """
    texto = (sufixo or "").strip().upper()
    if not texto:
        return ""
    if re.search(r"[RG]", texto):
        return "Marina"
    codigos = set(re.findall(r"\d{4}", texto))
    if not codigos:
        return _PROJETISTA_DEFAULT
    for nome, lista in _PROJETISTA_SUFFIX_MAP.items():
        if codigos & lista:
            return nome
    return _PROJETISTA_DEFAULT


def _resolve_projetista_user(user_model, sufixo: str):
    """
    Resolve o objeto User do projetista responsável baseado no sufixo.
    
    Usa _resolve_projetista_nome para obter o nome e depois busca
    o usuário correspondente no banco de dados.
    
    Args:
        user_model: Modelo de usuário do Django
        sufixo: String com sufixo do dispositivo
        
    Returns:
        User: Objeto do usuário projetista ou None se não encontrado
    """
    nome = _resolve_projetista_nome(sufixo)
    if not nome:
        return None
    partes = nome.split(" ", 1)
    primeiro = partes[0]
    ultimo = partes[1] if len(partes) > 1 else ""
    qs = user_model.objects.filter(groups__name="PROJETISTA", first_name__iexact=primeiro)
    if ultimo:
        qs = qs.filter(last_name__iexact=ultimo)
    else:
        qs = qs.filter(last_name__in=["", None])
    return qs.first()


def in_group(user, group_name: str) -> bool:
    """
    Verifica se um usuário pertence a um grupo específico.
    
    Args:
        user: Objeto User do Django
        group_name: Nome do grupo (ex: "ADMIN", "PROJETISTA")
        
    Returns:
        bool: True se autenticado E pertence ao grupo, False caso contrário
    """
    return user.is_authenticated and user.groups.filter(name=group_name).exists()


def group_required(group_name: str):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not in_group(request.user, group_name):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def _is_admin_user(user) -> bool:
    return user.is_authenticated and (user.is_superuser or in_group(user, "ADMIN"))


def _require_group_or_admin(request, group_name: str) -> bool:
    if _is_admin_user(request.user):
        return True
    if in_group(request.user, group_name):
        return False
    raise PermissionDenied


def _filter_solicitacoes_por_usuario(qs, user):
    """Filtra um QuerySet por um campo de usuário existente.

    Procura por campos comuns que armazenam o usuário (ex: "criado_por", "solicitante")
    e, se existir, retorna o QuerySet filtrado por esse campo. Caso nenhum campo
    seja encontrado, retorna o QuerySet original.
    """
    candidate_user_fields = [
        "criado_por",
        "solicitante",
        "requester",
        "usuario",
        "user",
        "created_by",
        "owner",
    ]
    for fname in candidate_user_fields:
        try:
            qs.model._meta.get_field(fname)
            return qs.filter(**{fname: user})
        except Exception:
            continue
    return qs


def _filter_solicitacoes_por_projetista(qs, user):
    """Filtra um QuerySet usando campos que representam o projetista responsavel."""
    candidate_fields = [
        "atribuido_para",
        "projetista",
        "designer",
        "responsavel",
        "assigned_to",
        "owner",
        "created_by",
        "user",
    ]
    for fname in candidate_fields:
        try:
            qs.model._meta.get_field(fname)
            return qs.filter(**{fname: user})
        except Exception:
            continue
    return qs.none()


def _cancel_rascunhos(qs, usuario, comentario=None):
    if qs is None:
        return 0
    rascunhos = list(qs.filter(status=SolicitacaoStatus.RASCUNHO))
    if not rascunhos:
        return 0
    comentario_final = (
        comentario
        or "Cancelado automaticamente: status 'Em espera' descontinuado."
    )
    for solicitacao in rascunhos:
        solicitacao.mudar_status(
            SolicitacaoStatus.CANCELADO,
            usuario,
            comentario=comentario_final,
        )
    return len(rascunhos)

def _build_week_windows(reference, count=6):
    """Constrói janelas semanais a partir de uma data de referência.

    Retorna uma lista com dicionários contendo label, start e end para cada semana.
    """
    local = timezone.localtime(reference)
    start = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    windows = []
    for i in range(count):
        window_start = start - timedelta(weeks=(count - 1 - i))
        window_end = window_start + timedelta(weeks=1)
        windows.append({"label": window_start.strftime("%d %b"), "start": window_start, "end": window_end})
    return windows


def _build_month_windows(reference, count=6):
    """Constrói janelas mensais a partir de uma data de referência.

    Gera 'count' janelas, cada uma representando o mês completo.
    """
    local = timezone.localtime(reference)
    tzinfo = local.tzinfo
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    windows = []

    def shift_months(base, offset):
        total_months = base.year * 12 + (base.month - 1) + offset
        year = total_months // 12
        month = total_months % 12 + 1
        return datetime(year, month, 1, tzinfo=tzinfo)

    for i in range(count):
        window_start = shift_months(start, -(count - 1 - i))
        window_end = shift_months(window_start, 1)
        windows.append({"label": window_start.strftime("%b %Y"), "start": window_start, "end": window_end})
    return windows


def _build_year_windows(reference, count=6):
    """Constrói janelas anuais a partir de uma data de referência.

    Cada janela representa um ano completo.
    """
    local = timezone.localtime(reference)
    tzinfo = local.tzinfo
    start = local.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    windows = []
    for i in range(count):
        year = start.year - (count - 1 - i)
        window_start = datetime(year, 1, 1, tzinfo=tzinfo)
        window_end = datetime(year + 1, 1, 1, tzinfo=tzinfo)
        windows.append({"label": str(year), "start": window_start, "end": window_end})
    return windows


def _build_status_time_series(
    Solicitacao=None,
    queryset=None,
    reference=None,
    count=6,
    windows=None,
    lines=None,
):
    """Constroi séries temporais agregando contagens por status para janelas.

    Pode usar um QuerySet fornecido ou o modelo `Solicitacao` para gerar
    contagens por status em cada janela (semana/mes/ano).
    """
    reference = reference or timezone.now()
    effective_lines = lines or _STATUS_TREND_LINES
    if windows is None:
        windows = {
            "semana": _build_week_windows(reference, count),
            "mes": _build_month_windows(reference, count),
            "ano": _build_year_windows(reference, count),
        }
    base_qs = queryset
    if base_qs is None and Solicitacao is not None:
        base_qs = Solicitacao.objects.all()
    series = {}
    for period_key, period_windows in windows.items():
        period_series = []
        for window in period_windows:
            counts = {line["key"]: 0 for line in effective_lines}
            if base_qs is not None:
                qs_window = base_qs.filter(
                    criado_em__gte=window["start"],
                    criado_em__lt=window["end"],
                )
                window_status_counts = (
                    qs_window.values("status").annotate(count=models.Count("pk"))
                )
                status_map = {entry["status"]: entry["count"] for entry in window_status_counts}
                for line in effective_lines:
                    counts[line["key"]] = sum(
                        status_map.get(status, 0) for status in line["statuses"]
                    )
            period_series.append({"label": window["label"], "counts": counts})
        series[period_key] = period_series
    return series


def _build_solicitante_week_windows(reference=None, days=7):
    """Constrói janelas diárias para o painel do solicitante (padrão: 7 dias)."""
    reference = reference or timezone.now()
    local = timezone.localtime(reference)
    today = local.replace(hour=0, minute=0, second=0, microsecond=0)
    total_days = max(1, int(days))
    windows = []
    for offset in range(total_days - 1, -1, -1):
        start = today - timedelta(days=offset)
        end = start + timedelta(days=1)
        label = f"{_PT_WEEKDAY_LABELS[start.weekday()]} {start.day:02d}"
        windows.append({"label": label, "start": start, "end": end})
    return windows


def _build_solicitante_month_windows(reference=None):
    """Constrói janelas diárias para o mês corrente (painel do solicitante)."""
    reference = reference or timezone.now()
    local = timezone.localtime(reference)
    tzinfo = local.tzinfo
    start_of_month = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_in_month = calendar.monthrange(local.year, local.month)[1]
    windows = []
    for day_offset in range(days_in_month):
        start = start_of_month + timedelta(days=day_offset)
        end = start + timedelta(days=1)
        label = f"{start.day:02d}"
        windows.append({"label": label, "start": start, "end": end})
    return windows


def _build_solicitante_year_windows(reference=None):
    """Constrói janelas mensais para o ano corrente (painel do solicitante)."""
    reference = reference or timezone.now()
    local = timezone.localtime(reference)
    tzinfo = local.tzinfo
    year = local.year
    windows = []
    for month in range(1, 13):
        start = datetime(year, month, 1, tzinfo=tzinfo)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=tzinfo)
        else:
            end = datetime(year, month + 1, 1, tzinfo=tzinfo)
        label = _PT_MONTH_ABBR[month - 1]
        windows.append({"label": label, "start": start, "end": end})
    return windows


def _build_solicitante_period_windows(reference=None):
    return {
        "semana": _build_solicitante_week_windows(reference, days=7),
        "mes": _build_solicitante_month_windows(reference),
        "ano": _build_solicitante_year_windows(reference),
    }


def _build_admin_trend_windows(reference=None, week_count=6):
    """Build admin trend windows for week/month/year views."""
    reference = reference or timezone.now()
    return {
        "semana": _build_week_windows(reference, week_count),
        "mes": _build_solicitante_month_windows(reference),
        "ano": _build_solicitante_year_windows(reference),
    }


def _safe_percentage(value, total):
    """Calcula porcentagem com proteção contra divisão por zero.

    Retorna 0 se total <= 0, caso contrário retorna a porcentagem com 1 casa decimal.
    """
    if total <= 0:
        return 0
    return round((value / total) * 100, 1)


def _build_solicitante_period_kpis(queryset, windows):
    """Calcula KPIs agregados por período (semana/mes/ano)."""
    kpis = {}
    if queryset is None:
        return kpis

    def _period_span(window_list):
        if not window_list:
            return None, None
        return window_list[0]["start"], window_list[-1]["end"]

    def _average_finalization_days(items):
        if not items:
            return None
        total_seconds = sum(items)
        avg_seconds = total_seconds / len(items)
        return round(avg_seconds / 86400, 1)

    for period_key, period_windows in (windows or {}).items():
        period_start, period_end = _period_span(period_windows)
        if not period_start or not period_end:
            kpis[period_key] = {
                "total_novas": 0,
                "media_por_dia": 0,
                "aprovacao_pct": 0,
                "finalizacao_pct": 0,
                "tempo_medio_dias": None,
            }
            continue

        total_novas = queryset.filter(
            criado_em__gte=period_start,
            criado_em__lt=period_end,
        ).count()

        total_days = max(1, (period_end - period_start).days)
        media_por_dia = round(total_novas / total_days, 1)

        aprovados = queryset.filter(
            aprovado_em__gte=period_start,
            aprovado_em__lt=period_end,
        ).count()
        reprovados = queryset.filter(
            reprovado_em__gte=period_start,
            reprovado_em__lt=period_end,
        ).count()
        cancelados = queryset.filter(
            cancelado_em__gte=period_start,
            cancelado_em__lt=period_end,
        ).count()
        total_decisoes = aprovados + reprovados + cancelados
        aprovacao_pct = _safe_percentage(aprovados, total_decisoes)

        finalizadas = queryset.filter(
            concluido_em__gte=period_start,
            concluido_em__lt=period_end,
        ).count()
        finalizacao_pct = _safe_percentage(finalizadas, total_novas)

        final_times = []
        final_qs = queryset.filter(
            concluido_em__gte=period_start,
            concluido_em__lt=period_end,
        ).values_list("criado_em", "concluido_em")
        for criado_em, concluido_em in final_qs:
            if concluido_em and criado_em:
                delta = concluido_em - criado_em
                final_times.append(delta.total_seconds())

        tempo_medio_dias = _average_finalization_days(final_times)

        kpis[period_key] = {
            "total_novas": total_novas,
            "media_por_dia": media_por_dia,
            "aprovacao_pct": aprovacao_pct,
            "finalizacao_pct": finalizacao_pct,
            "tempo_medio_dias": tempo_medio_dias,
        }

    return kpis


def _build_solicitante_trend_payload(queryset, reference=None):
    if queryset is None:
        return {"periods": {}, "statuses": [], "default_period": "mes", "kpis": {}}
    reference = reference or timezone.now()
    windows = _build_solicitante_period_windows(reference)
    series = _build_status_time_series(
        queryset=queryset,
        reference=reference,
        windows=windows,
        lines=_SOLICITANTE_TREND_LINES,
    )

    def _window_dates(period_key):
        window_list = windows.get(period_key, [])
        return [window["start"].date().isoformat() for window in window_list]

    periods = {}
    for period_key, entries in series.items():
        labels = [entry["label"] for entry in entries]
        status_series = {line["key"]: [] for line in _SOLICITANTE_TREND_LINES}
        totals = []
        for entry in entries:
            counts = entry["counts"]
            window_total = sum(counts.get(key, 0) for key in status_series)
            totals.append(window_total)
            for key in status_series:
                status_series[key].append(_safe_percentage(counts.get(key, 0), window_total))
        dates = _window_dates(period_key)
        periods[period_key] = {
            "labels": labels,
            "series": status_series,
            "totals": totals,
            "dates": dates[: len(labels)],
        }
    kpis = _build_solicitante_period_kpis(queryset, windows)
    # Fallback: inject demo data so the solicitante dashboard renders a chart similar ao projetista
    def _periods_have_data(periods_dict):
        for period in periods_dict.values():
            series_map = period.get("series") or {}
            for values in series_map.values():
                for value in values or []:
                    if value not in (0, None):
                        return True
        return False

    def _build_fallback_dates(period_key, labels):
        local = timezone.localtime(reference)
        if period_key == "semana":
            windows_local = _build_solicitante_week_windows(reference)
            dates_local = [window["start"].date().isoformat() for window in windows_local]
            return dates_local[: len(labels)]
        if period_key == "mes":
            year = local.year
            month = local.month
            dates_local = []
            for label in labels:
                try:
                    day = int(str(label)[:2])
                    dates_local.append(date(year, month, day).isoformat())
                except (TypeError, ValueError):
                    dates_local.append("")
            return dates_local
        if period_key == "ano":
            year = local.year
            dates_local = []
            for label in labels:
                month = None
                if label in _PT_MONTH_ABBR:
                    month = _PT_MONTH_ABBR.index(label) + 1
                else:
                    try:
                        month = int(str(label)[:2])
                    except (TypeError, ValueError):
                        month = None
                if month:
                    dates_local.append(date(year, month, 1).isoformat())
                else:
                    dates_local.append("")
            return dates_local
        return []

    if not _periods_have_data(periods):
        fake_statuses = ["pendente", "aprovacao", "retrabalho", "aprovado", "cancelado"]

        def build_fake(labels, data, period_key):
            series_map = {}
            totals_local = []
            for key in fake_statuses:
                series_map[key] = data.get(key, [0] * len(labels))
            for idx in range(len(labels)):
                totals_local.append(sum(series_map[key][idx] for key in fake_statuses))
            return {
                "labels": labels,
                "series": series_map,
                "totals": totals_local,
                "dates": _build_fallback_dates(period_key, labels),
            }

        week_windows = _build_solicitante_week_windows(reference, days=7)
        week_labels = [window["label"] for window in week_windows]
        base_week_data = {
            "pendente": [28, 26, 25, 24, 24, 23, 22],
            "aprovacao": [18, 18, 19, 19, 20, 21, 22],
            "retrabalho": [10, 11, 12, 12, 12, 13, 14],
            "aprovado": [34, 35, 35, 36, 36, 36, 35],
            "cancelado": [10, 10, 9, 9, 8, 7, 7],
        }
        week_data = {
            key: (values * 3)[: len(week_labels)]
            for key, values in base_week_data.items()
        }

        month_labels = [f"{day:02d}" for day in range(1, 31, 3)] + ["30"]
        month_data = {
            "pendente": [26, 25, 24, 23, 24, 24, 25, 26, 27, 26, 25],
            "aprovacao": [18, 18, 19, 19, 20, 21, 22, 21, 21, 20, 19],
            "retrabalho": [11, 11, 12, 12, 12, 13, 13, 13, 12, 12, 12],
            "aprovado": [35, 36, 36, 37, 36, 35, 34, 34, 33, 32, 33],
            "cancelado": [10, 10, 9, 9, 8, 7, 6, 6, 7, 10, 11],
        }

        year_labels = _PT_MONTH_ABBR
        year_data = {
            "pendente": [24, 25, 25, 24, 23, 22, 23, 24, 25, 26, 27, 26],
            "aprovacao": [18, 18, 19, 19, 20, 21, 22, 22, 21, 20, 19, 18],
            "retrabalho": [10, 11, 12, 12, 12, 13, 13, 13, 12, 12, 11, 11],
            "aprovado": [38, 36, 35, 36, 37, 36, 35, 34, 33, 32, 33, 34],
            "cancelado": [10, 10, 9, 9, 8, 8, 7, 7, 9, 10, 10, 11],
        }

        periods = {
            "semana": build_fake(week_labels, week_data, "semana"),
            "mes": build_fake(month_labels, month_data, "mes"),
            "ano": build_fake(year_labels, year_data, "ano"),
        }
    return {
        "periods": periods,
        "statuses": [
            {
                "key": line["key"],
                "label": line["label"],
                "color": line.get("color"),
                "fill": line.get("fill"),
            }
            for line in _SOLICITANTE_TREND_LINES
        ],
        "default_period": "mes",
        "kpis": kpis,
    }


def _resolve_user_label(user, fallback: str):
    if not user:
        return fallback
    label = ""
    try:
        label = user.get_full_name() or ""
    except Exception:
        label = ""
    label = label.strip()
    if label:
        return label
    username = getattr(user, "username", "") or ""
    if username:
        return username
    return str(user) if user else fallback


def _build_solicitante_age_entries(queryset, reference=None, limit=28):
    if queryset is None:
        return []
    try:
        status_field = queryset.model._meta.get_field("status")
        if not isinstance(status_field, (models.CharField, models.TextField)):
            return []
    except Exception:
        return []

    reference = reference or timezone.now()
    now_local = timezone.localtime(reference)
    chart_statuses = [
        SolicitacaoStatus.EM_FILA,
        SolicitacaoStatus.EM_PROJETO,
        SolicitacaoStatus.RETRABALHO,
        SolicitacaoStatus.AGUARDANDO_APROVACAO,
    ]
    chart_limit = max(1, int(limit))
    pre_limit = max(chart_limit * 2, chart_limit)
    chart_qs = list(
        queryset.filter(status__in=chart_statuses)
        .select_related("criado_por", "atribuido_para")
        .order_by("criado_em")[:pre_limit]
    )
    if not chart_qs:
        return []

    gv_proj_map = _build_gv_proj_map(chart_qs)
    rows = []
    for sol in chart_qs:
        if not sol.criado_em:
            continue
        created_local = timezone.localtime(sol.criado_em)
        created_label = created_local.strftime("%d/%m")
        age_seconds = max((now_local - created_local).total_seconds(), 0)
        age_days = age_seconds / 86400
        age_hours = age_seconds / 3600
        display_id = gv_proj_map.get(sol.id) or sol.job or f"#{sol.id}"
        projetista_label = _resolve_user_label(sol.atribuido_para, "Sem projetista")
        entry = {
            "id": sol.id,
            "display_id": display_id,
            "created_label": created_label,
            "label": f"{display_id} - {created_label}",
            "created_at": created_local.isoformat(),
            "age_days": round(age_days, 2),
            "age_hours": round(age_hours, 2),
            "projetista_label": projetista_label,
        }
        group_sort = projetista_label.lower()
        rows.append(
            (
                projetista_label == "Sem projetista",
                group_sort,
                created_local,
                entry,
            )
        )

    rows.sort(key=lambda item: (item[0], item[1], item[2]))
    entries = [row[3] for row in rows][:chart_limit]
    return entries


def _get_solicitante_dashboard_extras(user, include_all: bool = False, reference=None):
    extras = {
        "solicitante_trend_payload": {"periods": {}, "statuses": [], "default_period": "mes"},
        "solicitante_chart_entries": [],
    }
    try:
        SolicitacaoModel = apps.get_model("portal", "Solicitacao")
    except LookupError:
        return extras

    queryset = SolicitacaoModel.objects.all()
    if not include_all:
        queryset = _filter_solicitacoes_por_usuario(queryset, user)
    extras["solicitante_trend_payload"] = _build_solicitante_trend_payload(
        queryset, reference=reference or timezone.now()
    )
    extras["solicitante_chart_entries"] = _build_solicitante_age_entries(
        queryset, reference=reference or timezone.now()
    )
    extras.update(
        _get_solicitante_otd_otc_metrics(
            user,
            include_all=include_all,
            reference=reference or timezone.now(),
            prazo_dias=10,
        )
    )
    return extras


def _decorate_solicitacao(solicitacao, gv_proj_map=None):
    """Adiciona atributos derivados para facilitar a exibição no template.

    Inclui status_label, status_key, status_class e display_id usados nas views/templates.
    """
    meta = _STATUS_META.get(solicitacao.status, None)
    if meta:
        solicitacao.status_label = meta["label"]
        solicitacao.status_key = meta["key"]
        solicitacao.status_class = meta["class"]
    else:
        solicitacao.status_label = solicitacao.status
        solicitacao.status_key = "outro"
        solicitacao.status_class = "muted"
    gv_proj_id = None
    if gv_proj_map is not None:
        gv_proj_id = gv_proj_map.get(solicitacao.id)
    if not gv_proj_id:
        gv_proj_id = _get_gv_proj_id_for_solicitacao(solicitacao)
    solicitacao.display_id = gv_proj_id or solicitacao.job or f"#{solicitacao.id}"
    return solicitacao


def _parse_gv_proj_id(value: str):
    """Analisa um valor GV_PROJ no formato YYYYNN e retorna (ano, seq) se válido."""
    if not value or not value.isdigit() or len(value) <= 4:
        return None
    year = int(value[:4])
    seq = int(value[4:] or 0)
    if year < 2000 or year > 2100 or seq <= 0:
        return None
    return year, seq


def _format_gv_proj_id(year: int, seq: int) -> str:
    """Formata o GV_PROJ no padrão YYYYNN (seq com pelo menos 2 dígitos)."""
    if not year or not seq:
        return ""
    seq_str = str(seq).zfill(2)
    return f"{year}{seq_str}"


def _resolve_gv_proj_to_solicitacao_id(value: str):
    """Resolve um GV_PROJ (YYYYNN) para o ID de Solicitação correspondente.

    Retorna None se inválido ou fora do intervalo.
    """
    parsed = _parse_gv_proj_id(value)
    if not parsed:
        return None
    year, seq = parsed
    qs = (
        Solicitacao.objects.filter(criado_em__year=year)
        .order_by("criado_em", "id")
        .values_list("id", flat=True)
    )
    try:
        return qs[seq - 1]
    except IndexError:
        return None


def _get_gv_proj_id_for_solicitacao(solicitacao):
    """
    Gera um ID sequencial único (GV_PROJ_ID) para uma solicitação.
    
    Formato: YYYYNN (ano + sequência)
    Exemplo: 202401, 202402, etc (primeira e segunda solicitação de 2024)
    
    Algoritmo:
    1. Extrai o ano da solicitação
    2. Conta quantas solicitações foram criadas antes desta no mesmo ano
    3. Combina ano + contador para gerar ID
    
    Args:
        solicitacao: Instância de Solicitacao
        
    Returns:
        str: ID no formato YYYYNN ou string vazia se não tiver data
    """
    if not solicitacao or not solicitacao.criado_em:
        return ""
    year = solicitacao.criado_em.year
    seq = Solicitacao.objects.filter(criado_em__year=year).filter(
        Q(criado_em__lt=solicitacao.criado_em)
        | Q(criado_em=solicitacao.criado_em, id__lte=solicitacao.id)
    ).count()
    if not seq:
        return ""
    return _format_gv_proj_id(year, seq)


def _build_gv_proj_map(solicitacoes):
    """
    Constrói um mapa de solicitações -> seus IDs sequenciais (GV_PROJ_ID).
    
    Otimizado para evitar N queries ao processar múltiplas solicitações.
    
    Args:
        solicitacoes: QuerySet ou lista de Solicitacao
        
    Returns:
        dict: Dicionário {solicitacao_id: gv_proj_id, ...}
    """
    if not solicitacoes:
        return {}
    years = {sol.criado_em.year for sol in solicitacoes if sol.criado_em}
    if not years:
        return {}
    rows = (
        Solicitacao.objects.filter(criado_em__year__in=years)
        .order_by("criado_em", "id")
        .values_list("id", "criado_em")
    )
    counts = {}
    mapping = {}
    for sol_id, criado_em in rows:
        year = criado_em.year
        counts[year] = counts.get(year, 0) + 1
        mapping[sol_id] = _format_gv_proj_id(year, counts[year])
    return mapping


def _get_solicitante_action(solicitacao):
    """
    Determina qual ação o solicitante pode realizar com uma solicitação.
    
    Baseado no status atual, retorna a view apropriada e label para o botão.
    
    Args:
        solicitacao: Instância de Solicitacao
        
    Returns:
        tuple: (nome_view, label_botao)
        Exemplo: ("aprovar_reaprovar", "Aprovar/Reprovar")
    """
    status_key = getattr(solicitacao, "status_key", "")
    if status_key == "aguardando_aprovacao":
        return "aprovar_reaprovar", "Aprovar/Reprovar"
    if status_key == "aprovado":
        return "retorno_final", "Retorno final"
    if status_key == "reprovado":
        return "solicitar_retrabalho", "Solicitar retrabalho"
    return "status_do_projeto", "Ver status"


def _get_solicitante_kpis(user):
    """
    Calcula KPIs (Key Performance Indicators) para o solicitante.
    
    Retorna contadores de solicitações em diferentes estados.
    Safe: trata erros se modelo não existir (útil em migrations).
    
    Args:
        user: Objeto User do Django
        
    Returns:
        tuple: (em_progresso, para_aprovar, retrabalho, aprovado)
               Exemplo: (5, 2, 1, 8)
    """
    in_progress = 0
    to_approve = 0
    rework = 0
    approved = 0

    try:
        Solicitacao = apps.get_model("portal", "Solicitacao")
    except LookupError:
        return in_progress, to_approve, rework, approved

    qs = _filter_solicitacoes_por_usuario(Solicitacao.objects.all(), user)

    try:
        status_field = Solicitacao._meta.get_field("status")
        if isinstance(status_field, (models.CharField, models.TextField)):
            in_progress = qs.filter(
                status__in=[SolicitacaoStatus.EM_FILA, SolicitacaoStatus.EM_PROJETO]
            ).count()

            to_approve = qs.filter(
                status=SolicitacaoStatus.AGUARDANDO_APROVACAO
            ).count()

            rework = qs.filter(
                status=SolicitacaoStatus.RETRABALHO
            ).count()

            approved = qs.filter(
                status__in=[SolicitacaoStatus.APROVADO, SolicitacaoStatus.CONCLUIDO]
            ).count()
    except Exception:
        pass

    return in_progress, to_approve, rework, approved


def _get_solicitante_status_counts(user, include_all: bool = False):
    """
    Calcula contadores de solicitações por status para o dashboard do solicitante.
    
    Args:
        user: Objeto User do Django
        include_all: Se True, mostra todas as solicitações (para admin)
                    Se False, mostra apenas as criadas pelo usuário
        
    Returns:
        dict: Dicionário com contadores por status
              Exemplo: {
                  "aguardando_projetista_count": 5,
                  "aguardando_aprovacao_count": 2,
                  ...
              }
    """
    counts = {
        "aguardando_projetista_count": 0,
        "aguardando_aprovacao_count": 0,
        "retrabalho_count": 0,
        "retorno_final_count": 0,
        "concluido_count": 0,
        "cancelado_count": 0,
        "total_count": 0,
    }

    try:
        Solicitacao = apps.get_model("portal", "Solicitacao")
    except LookupError:
        return counts

    qs = Solicitacao.objects.all()
    if not include_all:
        qs = _filter_solicitacoes_por_usuario(qs, user)
    _cancel_rascunhos(qs, user)

    counts["aguardando_projetista_count"] = qs.filter(
        status__in=[SolicitacaoStatus.EM_FILA, SolicitacaoStatus.EM_PROJETO]
    ).count()
    counts["aguardando_aprovacao_count"] = qs.filter(
        status=SolicitacaoStatus.AGUARDANDO_APROVACAO
    ).count()
    counts["retrabalho_count"] = qs.filter(status=SolicitacaoStatus.RETRABALHO).count()
    counts["retorno_final_count"] = qs.filter(
        status__in=[SolicitacaoStatus.APROVADO, SolicitacaoStatus.CONCLUIDO]
    ).count()
    counts["concluido_count"] = qs.filter(status=SolicitacaoStatus.CONCLUIDO).count()
    counts["cancelado_count"] = qs.filter(status=SolicitacaoStatus.CANCELADO).count()
    counts["total_count"] = qs.exclude(status=SolicitacaoStatus.CANCELADO).count()

    return counts


def _get_solicitante_otd_otc_metrics(
    user,
    include_all: bool = False,
    reference=None,
    prazo_dias: int = 10,
):
    metrics = {
        "otd_on_time": 0,
        "otd_late": 0,
        "otd_total": 0,
        "otd_percent": 0,
        "otd_target": 82,
        "otc_on_time": 0,
        "otc_late": 0,
        "otc_total": 0,
        "otc_percent": 0,
        "otc_target": 82,
        "prazo_dias": prazo_dias,
    }

    try:
        Solicitacao = apps.get_model("portal", "Solicitacao")
    except LookupError:
        return metrics

    def _pct(part, total):
        if total <= 0:
            return 0
        return int(round((part / total) * 100))

    queryset = Solicitacao.objects.all()
    if not include_all:
        queryset = _filter_solicitacoes_por_usuario(queryset, user)

    now_local = timezone.localtime(reference or timezone.now())
    cutoff = now_local - timedelta(days=prazo_dias)

    open_statuses = [
        SolicitacaoStatus.EM_FILA,
        SolicitacaoStatus.EM_PROJETO,
        SolicitacaoStatus.AGUARDANDO_APROVACAO,
        SolicitacaoStatus.RETRABALHO,
    ]
    open_qs = queryset.filter(status__in=open_statuses).exclude(criado_em__isnull=True)
    metrics["otd_on_time"] = open_qs.filter(criado_em__gte=cutoff).count()
    metrics["otd_late"] = open_qs.filter(criado_em__lt=cutoff).count()
    metrics["otd_total"] = metrics["otd_on_time"] + metrics["otd_late"]
    metrics["otd_percent"] = _pct(metrics["otd_on_time"], metrics["otd_total"])

    concluidos = list(
        queryset.filter(status=SolicitacaoStatus.CONCLUIDO)
        .exclude(criado_em__isnull=True)
    )
    otc_on_time = 0
    otc_late = 0
    for sol in concluidos:
        fim = sol.concluido_em or sol.atualizado_em or sol.criado_em
        if not fim or not sol.criado_em:
            continue
        created_local = timezone.localtime(sol.criado_em)
        end_local = timezone.localtime(fim)
        delta_days = (end_local - created_local).total_seconds() / 86400
        if delta_days <= prazo_dias:
            otc_on_time += 1
        else:
            otc_late += 1
    metrics["otc_on_time"] = otc_on_time
    metrics["otc_late"] = otc_late
    metrics["otc_total"] = otc_on_time + otc_late
    metrics["otc_percent"] = _pct(metrics["otc_on_time"], metrics["otc_total"])

    return metrics


def _parse_date(value: str):
    """Tenta parsear uma string no formato YYYY-MM-DD para date.

    Retorna None se inválido ou vazio.
    """
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_datetime(value: str):
    """Tenta parsear uma string ISO ou YYYY-MM-DD para datetime.

    Retorna um datetime timezone-aware se USE_TZ estiver habilitado.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
    if settings.USE_TZ and timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def _parse_int(value, default=0):
    """Converte para inteiro com fallback (default) em caso de erro."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _baseline_priority_order():
    """Retorna expressão ORDER BY para priorizar baseline_ame nulo, depois por baseline_ame e criado_em."""
    return [
        models.Case(
            models.When(baseline_ame__isnull=True, then=1),
            default=0,
            output_field=models.IntegerField(),
        ),
        "baseline_ame",
        "criado_em",
    ]


def _apply_q_filter(qs, q_filter: str):
    """Aplica um filtro de busca textual (q) ao QuerySet.

    Suporta busca por texto em título/descrição/job/sufixo e por ID/GV_PROJ numérico.
    """
    if not q_filter:
        return qs
    q_obj = (
        Q(titulo__icontains=q_filter)
        | Q(descricao__icontains=q_filter)
        | Q(job__icontains=q_filter)
        | Q(sufixo__icontains=q_filter)
    )
    if q_filter.isdigit():
        q_obj = q_obj | Q(id=int(q_filter))
        gv_match = _resolve_gv_proj_to_solicitacao_id(q_filter)
        if gv_match:
            q_obj = q_obj | Q(id=gv_match)
    return qs.filter(q_obj)


def _serialize_inline_value(value):
    """Serializa valores para edição inline (converte datas/horas para ISO)."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _format_inline_display(solicitacao, field_name, raw_value):
    """Formata o valor para exibição inline baseado no campo.

    Trata campos especiais como status, prioridade, datas e relacionamentos.
    """
    if field_name == "status":
        meta = _STATUS_META.get(solicitacao.status)
        return meta["label"] if meta else solicitacao.get_status_display()
    if field_name == "prioridade":
        return solicitacao.get_prioridade_display()
    if field_name == "id":
        display_id = getattr(solicitacao, "display_id", "")
        return display_id or getattr(solicitacao, "id", None)
    if field_name in {
        "criado_por",
        "atribuido_para",
        "aprovado_por",
        "reprovado_por",
        "retrabalho_por",
        "cancelado_por",
        "concluido_por",
    }:
        usuario = getattr(solicitacao, field_name, None)
        return getattr(usuario, "username", "") or ""
    if field_name == "anexos":
        file_name = getattr(raw_value, "name", "") if raw_value else ""
        return Path(file_name).name if file_name else ""
    if field_name in {
        "solicitado_em",
        "criado_em",
        "atualizado_em",
        "aprovado_em",
        "reprovado_em",
        "retrabalho_em",
        "cancelado_em",
        "concluido_em",
    }:
        if raw_value:
            return timezone.localtime(raw_value).strftime("%Y-%m-%d %H:%M")
        return ""
    if field_name in {"baseline_ame", "baseline_producao"}:
        if raw_value:
            return raw_value.strftime("%Y-%m-%d")
        return ""
    if field_name == "prazo_estimado":
        if raw_value:
            return raw_value.strftime("%Y-%m-%d")
        return ""
    if raw_value is None or raw_value == "":
        return ""
    return str(raw_value).strip()


def _get_inline_raw_value(solicitacao, field_name):
    """Retorna o valor cru usado para edição inline (ex: username para relacionamentos)."""
    if field_name in {
        "criado_por",
        "atribuido_para",
        "aprovado_por",
        "reprovado_por",
        "retrabalho_por",
        "cancelado_por",
        "concluido_por",
    }:
        usuario = getattr(solicitacao, field_name, None)
        return getattr(usuario, "username", "")
    return getattr(solicitacao, field_name, None)


def _build_inline_rows(solicitacoes):
    """Gera estrutura de linhas/células para edição inline no admin/table view."""
    rows = []
    for sol in solicitacoes:
        cells = {}
        for field in _INLINE_FIELD_CONFIG:
            raw_value = _get_inline_raw_value(sol, field["name"])
            cells[field["name"]] = {
                "value": _serialize_inline_value(raw_value),
                "display": _format_inline_display(sol, field["name"], raw_value),
            }
        rows.append({"solicitacao": sol, "cells": cells})
    return rows


def _parse_inline_value(field_name, raw_value, status_values, priority_values):
    """Valida e converte valores vindos da edição inline conforme o tipo de campo."""
    raw_value = raw_value or ""
    field_meta = _INLINE_FIELD_MAP.get(field_name, {})
    field_type = field_meta.get("type")
    if field_type == "select":
        choices_key = field_meta.get("choices_key")
        if choices_key == "status":
            if raw_value in status_values:
                return raw_value, None
            return None, "Status inválido."
        if choices_key == "prioridade":
            if raw_value.isdigit():
                valor = int(raw_value)
                if valor in priority_values:
                    return valor, None
            return None, "Prioridade inválida."
    if field_type == "number":
        try:
            valor = int(raw_value)
        except ValueError:
            return None, "Valor numérico inválido."
        if field_name == "quantidade":
            valor = max(1, valor)
        return valor, None
    return raw_value, None


def _handle_inline_update(request, Solicitacao, status_values, priority_values):
    """Processa uma atualização inline via POST e retorna JSON de resultado.

    Valida campo, converte valor, salva o modelo e retorna representação atualizada.
    """
    solicitacao_id_raw = request.POST.get("solicitacao_id", "").strip()
    field_name = request.POST.get("field", "").strip()
    field_meta = _INLINE_FIELD_MAP.get(field_name)
    if not field_meta or not field_meta.get("editable"):
        return JsonResponse({"success": False, "error": "Campo não editável."}, status=400)
    if not solicitacao_id_raw.isdigit():
        return JsonResponse({"success": False, "error": "ID inválido."}, status=400)
    solicitacao = Solicitacao.objects.filter(id=int(solicitacao_id_raw)).first()
    if not solicitacao:
        return JsonResponse({"success": False, "error": "Solicitação não encontrada."}, status=404)
    raw_value = request.POST.get("value", "")
    parsed_value, error = _parse_inline_value(field_name, raw_value, status_values, priority_values)
    if error:
        return JsonResponse({"success": False, "error": error}, status=400)
    setattr(solicitacao, field_name, parsed_value)
    solicitacao.save(update_fields=[field_name])
    updated_raw = _get_inline_raw_value(solicitacao, field_name)
    return JsonResponse(
        {
            "success": True,
            "value": _serialize_inline_value(updated_raw),
            "display": _format_inline_display(solicitacao, field_name, updated_raw),
            "field": field_name,
            "solicitacao_id": solicitacao.id,
        }
    )


def _normalize_codigo_dispositivo(value: str) -> str:
    """Normaliza um código de dispositivo removendo caracteres não alfanuméricos e zeros à esquerda."""
    texto = re.sub(r"[^0-9A-Za-z]", "", (value or "").strip()).upper()
    if not texto:
        return ""
    if texto.isdigit():
        texto = texto.lstrip("0") or "0"
    return texto


def _get_projetista_kpis(user):
    """
    KPIs do projetista (safe):
    - fila: itens a preencher
    - em_projeto: itens em andamento
    - retrabalho: itens devolvidos
    - prontos: itens aguardando aprovacao do solicitante
    """
    data = {
        "fila_count": 0,
        "em_projeto_count": 0,
        "retrabalho_count": 0,
        "prontos_count": 0,
        "total_aberto": 0,
        "fila_urgente_count": 0,
        "em_projeto_urgente_count": 0,
        "retrabalho_urgente_count": 0,
        "fila_sem_atribuicao_count": 0,
        "em_projeto_atrasado_count": 0,
        "retrabalho_atrasado_count": 0,
        "chart_entries": [],
    }

    try:
        Solicitacao = apps.get_model("portal", "Solicitacao")
    except LookupError:
        return data

    qs = Solicitacao.objects.all()

    try:
        Solicitacao._meta.get_field("atribuido_para")
        qs = qs.filter(Q(atribuido_para=user) | Q(atribuido_para__isnull=True))
    except Exception:
        pass

    candidate_user_fields = [
        "projetista",
        "designer",
        "responsavel",
        "assigned_to",
        "owner",
        "created_by",
        "user",
    ]
    for fname in candidate_user_fields:
        try:
            Solicitacao._meta.get_field(fname)
            qs = qs.filter(**{fname: user})
            break
        except Exception:
            continue

    status_values = [
        SolicitacaoStatus.EM_FILA,
        SolicitacaoStatus.EM_PROJETO,
        SolicitacaoStatus.RETRABALHO,
        SolicitacaoStatus.AGUARDANDO_APROVACAO,
    ]

    try:
        status_field = Solicitacao._meta.get_field("status")
        if isinstance(status_field, (models.CharField, models.TextField)):
            data["fila_count"] = qs.filter(status=SolicitacaoStatus.EM_FILA).count()
            data["em_projeto_count"] = qs.filter(status=SolicitacaoStatus.EM_PROJETO).count()
            data["retrabalho_count"] = qs.filter(status=SolicitacaoStatus.RETRABALHO).count()
            data["prontos_count"] = qs.filter(status=SolicitacaoStatus.AGUARDANDO_APROVACAO).count()
            data["total_aberto"] = qs.filter(status__in=status_values).count()
    except Exception:
        return data

    try:
        prioridade_field = Solicitacao._meta.get_field("prioridade")
        if isinstance(prioridade_field, (models.IntegerField, models.SmallIntegerField)):
            urgentes = [Prioridade.ALTA, Prioridade.CRITICA]
            data["fila_urgente_count"] = qs.filter(
                status=SolicitacaoStatus.EM_FILA,
                prioridade__in=urgentes,
            ).count()
            data["em_projeto_urgente_count"] = qs.filter(
                status=SolicitacaoStatus.EM_PROJETO,
                prioridade__in=urgentes,
            ).count()
            data["retrabalho_urgente_count"] = qs.filter(
                status=SolicitacaoStatus.RETRABALHO,
                prioridade__in=urgentes,
            ).count()
    except Exception:
        pass

    try:
        Solicitacao._meta.get_field("atribuido_para")
        data["fila_sem_atribuicao_count"] = qs.filter(
            status=SolicitacaoStatus.EM_FILA,
            atribuido_para__isnull=True,
        ).count()
    except Exception:
        pass

    try:
        Solicitacao._meta.get_field("prazo_estimado")
        hoje = timezone.now().date()
        data["em_projeto_atrasado_count"] = qs.filter(
            status=SolicitacaoStatus.EM_PROJETO,
            prazo_estimado__isnull=False,
            prazo_estimado__lt=hoje,
        ).count()
        data["retrabalho_atrasado_count"] = qs.filter(
            status=SolicitacaoStatus.RETRABALHO,
            prazo_estimado__isnull=False,
            prazo_estimado__lt=hoje,
        ).count()
    except Exception:
        pass

    chart_entries = []
    chart_statuses = [
        SolicitacaoStatus.EM_FILA,
        SolicitacaoStatus.EM_PROJETO,
        SolicitacaoStatus.RETRABALHO,
    ]
    chart_limit = 28
    now_local = timezone.localtime()
    chart_qs = list(
        qs.filter(status__in=chart_statuses)
        .select_related("criado_por", "atribuido_para")
        .order_by("criado_em")[:chart_limit]
    )
    gv_proj_map = _build_gv_proj_map(chart_qs)
    for sol in chart_qs:
        created = sol.criado_em
        if not created:
            continue
        created_local = timezone.localtime(created)
        created_label = created_local.strftime("%d/%m")
        age_seconds = (now_local - created_local).total_seconds()
        age_seconds = max(age_seconds, 0)
        age_days = age_seconds / 86400
        age_hours = age_seconds / 3600
        title = (sol.titulo or "").strip()
        if not title:
            title = "Solicitação sem título"
        if len(title) > 45:
            trimmed = title[:42].rstrip()
            title = f"{trimmed}..." if trimmed else "Solicitação"
        display_id = gv_proj_map.get(sol.id) or sol.job or f"#{sol.id}"
        label = f"{display_id} - {created_label}"
        chart_entries.append(
            {
                "id": sol.id,
                "display_id": display_id,
                "created_label": created_label,
                "label": label,
                "created_at": created_local.isoformat(),
                "age_days": round(age_days, 2),
                "age_hours": round(age_hours, 2),
            }
        )
    data["chart_entries"] = chart_entries

    return data


def _get_projetista_dashboard_extras(user, include_all: bool = False, reference=None):
    """
    Retorna dados extras para o dashboard do projetista (trend chart, métricas, etc).
    Similar ao _get_solicitante_dashboard_extras mas adaptado para o fluxo do projetista.
    """
    extras = {
        "projetista_trend_payload": {"periods": {}, "statuses": [], "default_period": "mes"},
        "projetista_chart_entries": [],
    }
    try:
        SolicitacaoModel = apps.get_model("portal", "Solicitacao")
    except LookupError:
        return extras

    queryset = SolicitacaoModel.objects.all()
    if not include_all:
        queryset = queryset.filter(Q(atribuido_para=user) | Q(atribuido_para__isnull=True))
    
    extras["projetista_trend_payload"] = _build_projetista_trend_payload(
        queryset, reference=reference or timezone.now()
    )
    extras["projetista_chart_entries"] = _build_projetista_age_entries(
        queryset, reference=reference or timezone.now()
    )
    return extras


def _build_projetista_trend_payload(queryset, reference=None):
    """
    Constrói payload de trend chart para o projetista.
    Mostra evolução dos status: EM_FILA, EM_PROJETO, RETRABALHO, AGUARDANDO_APROVACAO.
    """
    if queryset is None:
        return {"periods": {}, "statuses": [], "default_period": "mes", "kpis": {}}
    
    reference = reference or timezone.now()
    windows = _build_solicitante_period_windows(reference)
    
    # Usar linhas de trend adaptadas para projetista
    projetista_trend_lines = [
        {"key": "fila", "label": "Fila (aguardando projeto)", "color": "#1b7355", "fill": "#1b735540"},
        {"key": "em_projeto", "label": "Em projeto", "color": "#2b8cc9", "fill": "#2b8cc940"},
        {"key": "retrabalho", "label": "Retrabalho", "color": "#f5a623", "fill": "#f5a62340"},
        {"key": "prontos", "label": "Pronto para aprovação", "color": "#27ae60", "fill": "#27ae6040"},
    ]
    
    series = _build_projetista_status_time_series(
        queryset=queryset,
        reference=reference,
        windows=windows,
        lines=projetista_trend_lines,
    )

    def _window_dates(period_key):
        window_list = windows.get(period_key, [])
        return [window["start"].date().isoformat() for window in window_list]

    periods = {}
    for period_key, entries in series.items():
        labels = [entry["label"] for entry in entries]
        status_series = {line["key"]: [] for line in projetista_trend_lines}
        totals = []
        for entry in entries:
            counts = entry["counts"]
            window_total = sum(counts.get(key, 0) for key in status_series)
            totals.append(window_total)
            for key in status_series:
                status_series[key].append(_safe_percentage(counts.get(key, 0), window_total))
        dates = _window_dates(period_key)
        periods[period_key] = {
            "labels": labels,
            "series": status_series,
            "totals": totals,
            "dates": dates[: len(labels)],
        }
    
    # Se não houver dados reais, usar dados de fallback
    def _periods_have_data(periods_dict):
        for period in periods_dict.values():
            series_map = period.get("series") or {}
            for values in series_map.values():
                for value in values or []:
                    if value not in (0, None):
                        return True
        return False

    if not _periods_have_data(periods):
        # Dados de fallback para projetista
        week_windows = _build_solicitante_week_windows(reference, days=7)
        week_labels = [window["label"] for window in week_windows]
        month_labels = [f"{day:02d}" for day in range(1, 31, 3)] + ["30"]
        year_labels = _PT_MONTH_ABBR

        periods = {
            "semana": {
                "labels": week_labels,
                "series": {
                    "fila": [22, 21, 20, 20, 19, 18, 18],
                    "em_projeto": [16, 17, 17, 18, 18, 19, 19],
                    "retrabalho": [8, 8, 9, 9, 9, 10, 10],
                    "prontos": [12, 13, 14, 14, 15, 15, 16],
                },
                "totals": [58, 59, 60, 61, 61, 62, 63],
                "dates": [window["start"].date().isoformat() for window in week_windows],
            },
            "mes": {
                "labels": month_labels,
                "series": {
                    "fila": [20, 19, 18, 17, 18, 18, 19, 20, 21, 20, 19],
                    "em_projeto": [17, 17, 18, 18, 19, 20, 20, 20, 19, 19, 18],
                    "retrabalho": [8, 9, 9, 9, 9, 9, 10, 10, 10, 10, 9],
                    "prontos": [13, 14, 15, 16, 15, 14, 14, 13, 12, 12, 13],
                },
                "totals": [58, 59, 60, 60, 61, 61, 63, 63, 62, 61, 59],
                "dates": [date(reference.year, reference.month, day).isoformat() 
                         for day in range(1, 31, 3)] + [date(reference.year, reference.month, 30).isoformat()],
            },
            "ano": {
                "labels": year_labels,
                "series": {
                    "fila": [20, 19, 19, 18, 18, 18, 19, 20, 21, 20, 19, 19],
                    "em_projeto": [17, 18, 18, 19, 19, 20, 20, 19, 19, 19, 18, 18],
                    "retrabalho": [9, 9, 9, 9, 9, 9, 10, 10, 10, 10, 9, 9],
                    "prontos": [14, 14, 14, 14, 15, 14, 13, 13, 12, 12, 14, 14],
                },
                "totals": [60, 60, 60, 60, 61, 61, 62, 62, 62, 61, 60, 60],
                "dates": [date(reference.year, month, 1).isoformat() for month in range(1, 13)],
            },
        }

    return {
        "periods": periods,
        "statuses": [
            {
                "key": line["key"],
                "label": line["label"],
                "color": line.get("color"),
                "fill": line.get("fill"),
            }
            for line in projetista_trend_lines
        ],
        "default_period": "mes",
    }


def _build_projetista_status_time_series(queryset, reference=None, windows=None, lines=None):
    """
    Constrói série temporal de status do projetista (EM_FILA, EM_PROJETO, RETRABALHO, AGUARDANDO_APROVACAO).
    Similar a _build_status_time_series mas com status específicos do projetista.
    """
    if queryset is None or windows is None:
        return {}
    
    status_mapping = {
        "fila": SolicitacaoStatus.EM_FILA,
        "em_projeto": SolicitacaoStatus.EM_PROJETO,
        "retrabalho": SolicitacaoStatus.RETRABALHO,
        "prontos": SolicitacaoStatus.AGUARDANDO_APROVACAO,
    }
    
    series = {}
    for period_name, period_windows in windows.items():
        entries = []
        for window in period_windows:
            window_qs = queryset.filter(
                criado_em__gte=window["start"],
                criado_em__lt=window["end"]
            )
            counts = {}
            for key, status in status_mapping.items():
                counts[key] = window_qs.filter(status=status).count()
            
            entries.append({
                "label": window["label"],
                "counts": counts,
            })
        series[period_name] = entries
    
    return series


def _build_projetista_age_entries(queryset, reference=None, limit=28):
    """
    Constrói lista de solicitações abertas do projetista ordenadas por idade.
    Mostra itens em EM_FILA, EM_PROJETO e RETRABALHO.
    """
    if queryset is None:
        return []
    
    try:
        status_field = queryset.model._meta.get_field("status")
        if not isinstance(status_field, (models.CharField, models.TextField)):
            return []
    except Exception:
        return []

    reference = reference or timezone.now()
    now_local = timezone.localtime(reference)
    chart_statuses = [
        SolicitacaoStatus.EM_FILA,
        SolicitacaoStatus.EM_PROJETO,
        SolicitacaoStatus.RETRABALHO,
    ]
    chart_limit = max(1, int(limit))
    pre_limit = max(chart_limit * 2, chart_limit)
    chart_qs = list(
        queryset.filter(status__in=chart_statuses)
        .select_related("criado_por", "atribuido_para")
        .order_by("criado_em")[:pre_limit]
    )
    if not chart_qs:
        return []

    gv_proj_map = _build_gv_proj_map(chart_qs)
    entries = []
    for sol in chart_qs:
        if not sol.criado_em:
            continue
        created_local = timezone.localtime(sol.criado_em)
        created_label = created_local.strftime("%d/%m")
        age_seconds = max((now_local - created_local).total_seconds(), 0)
        age_days = age_seconds / 86400
        age_hours = age_seconds / 3600
        display_id = gv_proj_map.get(sol.id) or sol.job or f"#{sol.id}"
        solicitante_label = _resolve_user_label(sol.criado_por, "Solicitante desconhecido")
        entry = {
            "id": sol.id,
            "display_id": display_id,
            "created_label": created_label,
            "label": f"{display_id} - {created_label}",
            "created_at": created_local.isoformat(),
            "age_days": round(age_days, 2),
            "age_hours": round(age_hours, 2),
            "solicitante_label": solicitante_label,
        }
        entries.append(entry)

    return entries[:chart_limit]


def _build_admin_solicitante_age_entries(queryset, reference=None, limit=None):
    """
    Constrói lista de solicitações abertas para o painel admin, agrupadas por solicitante.
    """
    if queryset is None:
        return []

    try:
        status_field = queryset.model._meta.get_field("status")
        if not isinstance(status_field, (models.CharField, models.TextField)):
            return []
    except Exception:
        return []

    reference = reference or timezone.now()
    now_local = timezone.localtime(reference)
    chart_statuses = [
        SolicitacaoStatus.EM_FILA,
        SolicitacaoStatus.EM_PROJETO,
        SolicitacaoStatus.RETRABALHO,
        SolicitacaoStatus.AGUARDANDO_APROVACAO,
    ]

    qs = (
        queryset.filter(status__in=chart_statuses)
        .select_related("criado_por", "atribuido_para")
        .order_by("criado_em")
    )
    if limit is not None:
        chart_limit = max(1, int(limit))
        qs = qs[:chart_limit]

    chart_qs = list(qs)
    if not chart_qs:
        return []

    gv_proj_map = _build_gv_proj_map(chart_qs)
    rows = []
    for sol in chart_qs:
        if not sol.criado_em:
            continue
        created_local = timezone.localtime(sol.criado_em)
        created_label = created_local.strftime("%d/%m")
        age_seconds = max((now_local - created_local).total_seconds(), 0)
        age_days = age_seconds / 86400
        age_hours = age_seconds / 3600
        display_id = gv_proj_map.get(sol.id) or sol.job or f"#{sol.id}"
        solicitante_label = _resolve_user_label(sol.criado_por, "Solicitante desconhecido")
        projetista_label = _resolve_user_label(sol.atribuido_para, "Sem projetista")
        entry = {
            "id": sol.id,
            "display_id": display_id,
            "created_label": created_label,
            "label": f"{display_id} - {created_label}",
            "created_at": created_local.isoformat(),
            "age_days": round(age_days, 2),
            "age_hours": round(age_hours, 2),
            "solicitante_label": solicitante_label,
            "projetista_label": projetista_label,
        }
        group_sort = solicitante_label.lower()
        rows.append(
            (
                solicitante_label == "Solicitante desconhecido",
                group_sort,
                created_local,
                entry,
            )
        )

    rows.sort(key=lambda item: (item[0], item[1], item[2]))
    return [row[3] for row in rows]



@login_required
def portal_redirect(request):
    """Redireciona o usuário autenticado para o dashboard apropriado baseado em seu grupo."""
    if in_group(request.user, "ADMIN"):
        return redirect("admin_dashboard")
    if in_group(request.user, "DISPOSITIVOS"):
        return redirect("dashboard_dispositivos")
    if in_group(request.user, "PROJETISTA"):
        return redirect("projetista_dashboard")
    if in_group(request.user, "SOLICITANTE"):
        return redirect("solicitante_dashboard")
    return redirect("login")


def _get_admin_dashboard_context():
    """Compila métricas e contadores usados no dashboard de administração.

    Retorna um dicionário com diversos KPIs (backlog, pendências, contadores por grupo etc.).
    """
    backlog_total = 0
    aprovacoes_pendentes = 0
    pendencias_criticas = 0
    solicitantes_total = 0
    solicitantes_pendente = 0
    solicitantes_aprovacao = 0
    solicitantes_retrabalho = 0
    solicitantes_aprovado = 0
    solicitantes_cancelado = 0
    solicitantes_pendente_pct = 0
    solicitantes_aprovacao_pct = 0
    solicitantes_retrabalho_pct = 0
    solicitantes_aprovado_pct = 0
    solicitantes_cancelado_pct = 0
    projetistas_total = 0
    projetistas_fila = 0
    projetistas_em_projeto = 0
    projetistas_retrabalho = 0
    projetistas_prontos = 0
    projetistas_fila_pct = 0
    projetistas_em_projeto_pct = 0
    projetistas_retrabalho_pct = 0
    dispositivos_total = 0
    dispositivos_abertos = 0
    dispositivos_andamento = 0
    dispositivos_pendencias = 0
    dispositivos_abertos_pct = 0
    dispositivos_andamento_pct = 0
    dispositivos_pendencias_pct = 0
    admin_solicitante_age_entries = []

    try:
        Solicitacao = apps.get_model("portal", "Solicitacao")
    except LookupError:
        Solicitacao = None
    qs = None

    if Solicitacao:
        qs = Solicitacao.objects.all()
        active_qs = qs.exclude(status__in=[SolicitacaoStatus.CANCELADO, SolicitacaoStatus.RASCUNHO])
        backlog_total = qs.count()
        aprovacoes_pendentes = qs.filter(status=SolicitacaoStatus.AGUARDANDO_APROVACAO).count()
        pendencias_criticas = qs.filter(
            status__in=[SolicitacaoStatus.RETRABALHO, SolicitacaoStatus.REPROVADO]
        ).count()
        solicitantes_pendente = active_qs.filter(
            status__in=[SolicitacaoStatus.EM_FILA, SolicitacaoStatus.EM_PROJETO]
        ).count()
        solicitantes_aprovacao = active_qs.filter(
            status=SolicitacaoStatus.AGUARDANDO_APROVACAO
        ).count()
        solicitantes_retrabalho = active_qs.filter(
            status=SolicitacaoStatus.RETRABALHO
        ).count()
        solicitantes_aprovado = active_qs.filter(
            status__in=[SolicitacaoStatus.APROVADO, SolicitacaoStatus.CONCLUIDO]
        ).count()
        solicitantes_cancelado = qs.filter(
            status__in=[SolicitacaoStatus.CANCELADO, SolicitacaoStatus.RASCUNHO]
        ).count()
        solicitantes_total = (
            solicitantes_pendente
            + solicitantes_aprovacao
            + solicitantes_retrabalho
            + solicitantes_aprovado
            + solicitantes_cancelado
        )

        projetistas_base_qs = qs.filter(
            status__in=[
                SolicitacaoStatus.EM_FILA,
                SolicitacaoStatus.EM_PROJETO,
                SolicitacaoStatus.RETRABALHO,
                SolicitacaoStatus.AGUARDANDO_APROVACAO,
            ]
        )
        projetistas_total = projetistas_base_qs.count()
        projetistas_fila = projetistas_base_qs.filter(status=SolicitacaoStatus.EM_FILA).count()
        projetistas_em_projeto = projetistas_base_qs.filter(status=SolicitacaoStatus.EM_PROJETO).count()
        projetistas_retrabalho = projetistas_base_qs.filter(
            status=SolicitacaoStatus.RETRABALHO
        ).count()
        projetistas_prontos = projetistas_base_qs.filter(
            status=SolicitacaoStatus.AGUARDANDO_APROVACAO
        ).count()

        dispositivos_base_qs = qs.exclude(numero_dispositivo__isnull=True).exclude(
            numero_dispositivo=""
        )
        dispositivos_active_qs = dispositivos_base_qs.exclude(
            status__in=[SolicitacaoStatus.CANCELADO, SolicitacaoStatus.RASCUNHO]
        )
        dispositivos_total = dispositivos_active_qs.count()
        dispositivos_abertos = dispositivos_active_qs.filter(
            status=SolicitacaoStatus.EM_FILA
        ).count()
        dispositivos_andamento = dispositivos_active_qs.filter(
            status=SolicitacaoStatus.EM_PROJETO
        ).count()
        dispositivos_pendencias = dispositivos_active_qs.filter(
            status__in=[
                SolicitacaoStatus.AGUARDANDO_APROVACAO,
                SolicitacaoStatus.RETRABALHO,
                SolicitacaoStatus.REPROVADO,
            ]
        ).count()

        def _pct(part, total):
            if total <= 0:
                return 0
            return int(round((part / total) * 100))

        solicitantes_pendente_pct = _pct(solicitantes_pendente, solicitantes_total)
        solicitantes_aprovacao_pct = _pct(solicitantes_aprovacao, solicitantes_total)
        solicitantes_retrabalho_pct = _pct(solicitantes_retrabalho, solicitantes_total)
        solicitantes_aprovado_pct = _pct(solicitantes_aprovado, solicitantes_total)
        solicitantes_cancelado_pct = _pct(solicitantes_cancelado, solicitantes_total)

        projetistas_fila_pct = _pct(projetistas_fila, projetistas_total)
        projetistas_em_projeto_pct = _pct(projetistas_em_projeto, projetistas_total)
        projetistas_retrabalho_pct = _pct(projetistas_retrabalho, projetistas_total)

        dispositivos_abertos_pct = _pct(dispositivos_abertos, dispositivos_total)
        dispositivos_andamento_pct = _pct(dispositivos_andamento, dispositivos_total)
        dispositivos_pendencias_pct = _pct(dispositivos_pendencias, dispositivos_total)

        entity_limit = 60
        User = get_user_model()

        def _build_solicitante_option(identifier, label, counts):
            total = counts.get("total", 0)
            pendente = counts.get("pendente", 0)
            aprovacao = counts.get("aprovacao", 0)
            retrabalho = counts.get("retrabalho", 0)
            aprovado = counts.get("aprovado", 0)
            cancelado = counts.get("cancelado", 0)
            aprovacoes_pendentes = counts.get("aprovacoes_pendentes")
            if aprovacoes_pendentes is None:
                aprovacoes_pendentes = aprovacao
            aprovado_pct = _pct(aprovado, total)
            cancelado_pct = _pct(cancelado, total)
            statuses = [
                {"key": "pendente", "label": "Pendente", "value": _pct(pendente, total)},
                {"key": "aprovacao", "label": "Em aprovação", "value": _pct(aprovacao, total)},
                {"key": "retrabalho", "label": "Retrabalho", "value": _pct(retrabalho, total)},
                {"key": "aprovado", "label": "Aprovado", "value": _pct(aprovado, total)},
                {"key": "cancelado", "label": "Cancelado", "value": _pct(cancelado, total)},
            ]
            return {
                "id": identifier,
                "label": label,
                "statuses": statuses,
                "meta": [
                    {"label": "Base total", "value": str(total)},
                    {"label": "Aprovadas", "value": f"{aprovado_pct}%"},
                    {"label": "Canceladas", "value": f"{cancelado_pct}%"},
                ],
                "panel": {
                    "tag": f"Base: {total}",
                    "metrics": {
                        "pendente": {"value": pendente, "pct": _pct(pendente, total)},
                        "aprovacao": {"value": aprovacao, "pct": _pct(aprovacao, total)},
                        "retrabalho": {"value": retrabalho, "pct": _pct(retrabalho, total)},
                        "aprovado": {"value": aprovado, "pct": _pct(aprovado, total)},
                        "cancelado": {"value": cancelado, "pct": _pct(cancelado, total)},
                    },
                    "foot": {
                        "total": total,
                        "aprovacoes_pendentes": aprovacoes_pendentes,
                    },
                },
                "backlog": total,
            }

        def _build_projetista_option(identifier, label, counts):
            total = counts.get("total", 0)
            fila = counts.get("fila", 0)
            em_projeto = counts.get("em_projeto", 0)
            retrabalho = counts.get("retrabalho", 0)
            prontos = counts.get("prontos", 0)
            fila_pct = _pct(fila, total)
            em_projeto_pct = _pct(em_projeto, total)
            retrabalho_pct = _pct(retrabalho, total)
            statuses = [
                {"key": "fila", "label": "Fila", "value": fila_pct},
                {"key": "em_projeto", "label": "Em projeto", "value": em_projeto_pct},
                {"key": "retrabalho", "label": "Retrabalho", "value": retrabalho_pct},
            ]
            return {
                "id": identifier,
                "label": label,
                "statuses": statuses,
                "meta": [
                    {"label": "Total aberto", "value": str(total)},
                    {"label": "Em projeto", "value": f"{em_projeto_pct}%"},
                    {"label": "Retrabalho", "value": f"{retrabalho_pct}%"},
                ],
                "panel": {
                    "tag": f"Base: {total}",
                    "metrics": {
                        "fila": {"value": fila, "pct": fila_pct},
                        "em_projeto": {"value": em_projeto, "pct": em_projeto_pct},
                        "retrabalho": {"value": retrabalho, "pct": retrabalho_pct},
                    },
                    "foot": {
                        "total": total,
                        "prontos": prontos,
                    },
                },
                "backlog": total,
            }

        def _build_dispositivo_option(identifier, label, counts):
            total = counts.get("total", 0)
            abertos = counts.get("abertos", 0)
            andamento = counts.get("andamento", 0)
            pendencias = counts.get("pendencias", 0)
            andamento_pct = _pct(andamento, total)
            pendencias_pct = _pct(pendencias, total)
            statuses = [
                {"key": "abertos", "label": "Abertos", "value": _pct(abertos, total)},
                {"key": "andamento", "label": "Em andamento", "value": andamento_pct},
                {"key": "pendencias", "label": "Pendências", "value": pendencias_pct},
            ]
            return {
                "id": identifier,
                "label": label,
                "statuses": statuses,
                "meta": [
                    {"label": "Dispositivos monitorados", "value": str(total)},
                    {"label": "Em andamento", "value": f"{andamento_pct}%"},
                    {"label": "Pendências", "value": f"{pendencias_pct}%"},
                ],
                "panel": {
                    "tag": f"Monitorados: {total}",
                    "metrics": {
                        "abertos": {"value": abertos, "pct": _pct(abertos, total)},
                        "andamento": {"value": andamento, "pct": andamento_pct},
                        "pendencias": {"value": pendencias, "pct": pendencias_pct},
                    },
                    "foot": {
                        "total": total,
                        "pendencias": pendencias,
                    },
                },
                "backlog": total,
            }

        solicitante_users = list(
            User.objects.filter(groups__name="SOLICITANTE")
            .order_by("first_name", "last_name", "username")[:entity_limit]
        )
        solicitante_profiles = [_build_solicitante_option("all", "Todos os solicitantes", {
            "total": solicitantes_total,
            "pendente": solicitantes_pendente,
            "aprovacao": solicitantes_aprovacao,
            "retrabalho": solicitantes_retrabalho,
            "aprovado": solicitantes_aprovado,
            "cancelado": solicitantes_cancelado,
            "aprovacoes_pendentes": aprovacoes_pendentes,
        })]
        for user in solicitante_users:
            user_qs = _filter_solicitacoes_por_usuario(Solicitacao.objects.all(), user)
            user_active = user_qs.exclude(
                status__in=[SolicitacaoStatus.CANCELADO, SolicitacaoStatus.RASCUNHO]
            )
            user_pendente = user_active.filter(
                status__in=[SolicitacaoStatus.EM_FILA, SolicitacaoStatus.EM_PROJETO]
            ).count()
            user_aprovacao = user_active.filter(
                status=SolicitacaoStatus.AGUARDANDO_APROVACAO
            ).count()
            user_retrabalho = user_active.filter(
                status=SolicitacaoStatus.RETRABALHO
            ).count()
            user_aprovado = user_active.filter(
                status__in=[SolicitacaoStatus.APROVADO, SolicitacaoStatus.CONCLUIDO]
            ).count()
            user_cancelado = user_qs.filter(
                status__in=[SolicitacaoStatus.CANCELADO, SolicitacaoStatus.RASCUNHO]
            ).count()
            user_total = (
                user_pendente
                + user_aprovacao
                + user_retrabalho
                + user_aprovado
                + user_cancelado
            )
            user_counts = {
                "total": user_total,
                "pendente": user_pendente,
                "aprovacao": user_aprovacao,
                "retrabalho": user_retrabalho,
                "aprovado": user_aprovado,
                "cancelado": user_cancelado,
                "aprovacoes_pendentes": user_aprovacao,
            }
            solicitante_profiles.append(
                _build_solicitante_option(
                    str(user.id),
                    user.get_full_name() or user.get_username(),
                    user_counts,
                )
            )

        def _filter_solicitacoes_por_projetista(qs, user):
            candidate_fields = [
                "atribuido_para",
                "projetista",
                "designer",
                "responsavel",
                "assigned_to",
                "owner",
                "created_by",
                "user",
            ]
            for fname in candidate_fields:
                try:
                    qs.model._meta.get_field(fname)
                    return qs.filter(**{fname: user})
                except Exception:
                    continue
            return qs.none()

        projetista_users = list(
            User.objects.filter(groups__name="PROJETISTA")
            .order_by("first_name", "last_name", "username")[:entity_limit]
        )
        pipeline_statuses = [
            SolicitacaoStatus.EM_FILA,
            SolicitacaoStatus.EM_PROJETO,
            SolicitacaoStatus.RETRABALHO,
            SolicitacaoStatus.AGUARDANDO_APROVACAO,
        ]
        projetista_profiles = [
            _build_projetista_option(
                "all",
                "Todos os projetistas",
                {
                    "total": projetistas_total,
                    "fila": projetistas_fila,
                    "em_projeto": projetistas_em_projeto,
                    "retrabalho": projetistas_retrabalho,
                    "prontos": projetistas_prontos,
                },
            )
        ]
        for user in projetista_users:
            user_qs = _filter_solicitacoes_por_projetista(Solicitacao.objects.all(), user)
            user_active = user_qs.filter(status__in=pipeline_statuses)
            user_counts = {
                "total": user_active.count(),
                "fila": user_active.filter(status=SolicitacaoStatus.EM_FILA).count(),
                "em_projeto": user_active.filter(status=SolicitacaoStatus.EM_PROJETO).count(),
                "retrabalho": user_active.filter(status=SolicitacaoStatus.RETRABALHO).count(),
                "prontos": user_active.filter(
                    status=SolicitacaoStatus.AGUARDANDO_APROVACAO
                ).count(),
            }
            projetista_profiles.append(
                _build_projetista_option(
                    str(user.id),
                    user.get_full_name() or user.get_username(),
                    user_counts,
                )
            )

        dispositivos_base_all = Solicitacao.objects.exclude(numero_dispositivo__isnull=True).exclude(
            numero_dispositivo=""
        )
        dispositivo_users = list(
            User.objects.filter(groups__name="DISPOSITIVOS")
            .order_by("first_name", "last_name", "username")[:entity_limit]
        )
        dispositivo_profiles = [
            _build_dispositivo_option(
                "all",
                "Todos os dispositivos",
                {
                    "total": dispositivos_total,
                    "abertos": dispositivos_abertos,
                    "andamento": dispositivos_andamento,
                    "pendencias": dispositivos_pendencias,
                },
            )
        ]
        for user in dispositivo_users:
            user_qs = _filter_solicitacoes_por_usuario(dispositivos_base_all, user)
            user_active = user_qs.exclude(
                status__in=[SolicitacaoStatus.CANCELADO, SolicitacaoStatus.RASCUNHO]
            )
            user_counts = {
                "total": user_active.count(),
                "abertos": user_active.filter(status=SolicitacaoStatus.EM_FILA).count(),
                "andamento": user_active.filter(status=SolicitacaoStatus.EM_PROJETO).count(),
                "pendencias": user_active.filter(
                    status__in=[
                        SolicitacaoStatus.AGUARDANDO_APROVACAO,
                        SolicitacaoStatus.RETRABALHO,
                        SolicitacaoStatus.REPROVADO,
                    ]
                ).count(),
            }
            dispositivo_profiles.append(
                _build_dispositivo_option(
                    str(user.id),
                    user.get_full_name() or user.get_username(),
                    user_counts,
                )
            )

        admin_dashboard_payload = {
            "categories": {
                "solicitante": {
                    "title": "Status dos solicitantes",
                    "description": "Pendente, em aprovação, retrabalho, aprovado e cancelado.",
                    "options": solicitante_profiles,
                },
                "projetista": {
                    "title": "Status dos projetistas",
                    "description": "Fila, em projeto e retrabalho no fluxo atual.",
                    "options": projetista_profiles,
                },
                "dispositivo": {
                    "title": "Status dos dispositivos",
                    "description": "Abertos, em andamento e pendências.",
                    "options": dispositivo_profiles,
                },
            }
        }
    else:
        admin_dashboard_payload = {"categories": {}}
    admin_trend_windows = _build_admin_trend_windows()
    status_time_series = _build_status_time_series(
        Solicitacao,
        queryset=qs,
        windows=admin_trend_windows,
    )
    admin_dashboard_payload.setdefault("trend", {})
    admin_dashboard_payload["trend"].update(
        {
            "status_series": status_time_series,
            "lines": [
                {"key": line["key"], "label": line["label"], "color": line["color"]}
                for line in _STATUS_TREND_LINES
            ],
            "default_period": "semana",
        }
    )

    if qs is not None:
        admin_solicitante_age_entries = _build_admin_solicitante_age_entries(
            qs, reference=timezone.now()
        )

    return {
        "backlog_total": backlog_total,
        "aprovacoes_pendentes": aprovacoes_pendentes,
        "pendencias_criticas": pendencias_criticas,
        "solicitantes_total": solicitantes_total,
        "solicitantes_pendente": solicitantes_pendente,
        "solicitantes_aprovacao": solicitantes_aprovacao,
        "solicitantes_retrabalho": solicitantes_retrabalho,
        "solicitantes_aprovado": solicitantes_aprovado,
        "solicitantes_cancelado": solicitantes_cancelado,
        "solicitantes_pendente_pct": solicitantes_pendente_pct,
        "solicitantes_aprovacao_pct": solicitantes_aprovacao_pct,
        "solicitantes_retrabalho_pct": solicitantes_retrabalho_pct,
        "solicitantes_aprovado_pct": solicitantes_aprovado_pct,
        "solicitantes_cancelado_pct": solicitantes_cancelado_pct,
        "projetistas_total": projetistas_total,
        "projetistas_fila": projetistas_fila,
        "projetistas_em_projeto": projetistas_em_projeto,
        "projetistas_retrabalho": projetistas_retrabalho,
        "projetistas_prontos": projetistas_prontos,
        "projetistas_fila_pct": projetistas_fila_pct,
        "projetistas_em_projeto_pct": projetistas_em_projeto_pct,
        "projetistas_retrabalho_pct": projetistas_retrabalho_pct,
        "dispositivos_total": dispositivos_total,
        "dispositivos_abertos": dispositivos_abertos,
        "dispositivos_andamento": dispositivos_andamento,
        "dispositivos_pendencias": dispositivos_pendencias,
        "dispositivos_abertos_pct": dispositivos_abertos_pct,
        "dispositivos_andamento_pct": dispositivos_andamento_pct,
        "dispositivos_pendencias_pct": dispositivos_pendencias_pct,
        "status_bar_items": _STATUS_BAR_ITEMS,
        "admin_dashboard_payload": admin_dashboard_payload,
        "admin_solicitante_age_entries": admin_solicitante_age_entries,
    }


def _get_dispositivos_dashboard_context():
    ctx = {
        "abertos_count": 0,
        "andamento_count": 0,
        "pendencias_count": 0,
    }
    for idx in range(1, 12):
        ctx[f"tipo_{idx:02d}"] = 0

    try:
        Solicitacao = apps.get_model("portal", "Solicitacao")
    except LookupError:
        return ctx

    base_qs = Solicitacao.objects.exclude(numero_dispositivo__isnull=True).exclude(
        numero_dispositivo=""
    )
    active_qs = base_qs.exclude(status__in=[SolicitacaoStatus.CANCELADO, SolicitacaoStatus.RASCUNHO])

    ctx["abertos_count"] = active_qs.filter(
        status__in=[SolicitacaoStatus.EM_FILA]
    ).count()
    ctx["andamento_count"] = active_qs.filter(
        status=SolicitacaoStatus.EM_PROJETO
    ).count()
    ctx["pendencias_count"] = active_qs.filter(
        status__in=[
            SolicitacaoStatus.AGUARDANDO_APROVACAO,
            SolicitacaoStatus.RETRABALHO,
            SolicitacaoStatus.REPROVADO,
        ]
    ).count()

    return ctx


def _get_admin_trend_queryset(category, option_id, base_qs):
    if base_qs is None:
        return base_qs
    normalized_category = (category or "").strip().lower()
    normalized_option = (option_id or "all").strip()
    if normalized_category == "dispositivo":
        base_qs = base_qs.exclude(numero_dispositivo__isnull=True).exclude(
            numero_dispositivo=""
        )
    if normalized_category not in {"solicitante", "projetista", "dispositivo"}:
        return base_qs
    if not normalized_option or normalized_option.lower() == "all":
        return base_qs
    User = get_user_model()
    if normalized_category == "solicitante":
        try:
            target_user = User.objects.get(id=int(normalized_option))
        except (ValueError, User.DoesNotExist):
            return base_qs.none()
        return _filter_solicitacoes_por_usuario(base_qs, target_user)
    if normalized_category == "projetista":
        try:
            target_user = User.objects.get(id=int(normalized_option))
        except (ValueError, User.DoesNotExist):
            return base_qs.none()
        return _filter_solicitacoes_por_projetista(base_qs, target_user)
    if normalized_category == "dispositivo":
        try:
            target_user = User.objects.get(id=int(normalized_option))
        except (ValueError, User.DoesNotExist):
            return base_qs.none()
        return _filter_solicitacoes_por_usuario(base_qs, target_user)
    return base_qs


# =========================
# ADMIN (placeholder)
# =========================
@login_required
@group_required("ADMIN")
def admin_dashboard(request):
    return render(request, "portal/admin_dashboard.html", _get_admin_dashboard_context())


@login_required
@group_required("ADMIN")
def admin_dashboard_status_series(request):
    category = request.GET.get("category", "").strip()
    option_id = request.GET.get("option_id", "all").strip()
    try:
        Solicitacao = apps.get_model("portal", "Solicitacao")
    except LookupError:
        return JsonResponse({"status_series": {}}, status=200)
    base_qs = Solicitacao.objects.all()
    filtered_qs = _get_admin_trend_queryset(category, option_id, base_qs)
    admin_trend_windows = _build_admin_trend_windows()
    status_series = _build_status_time_series(
        Solicitacao,
        queryset=filtered_qs,
        windows=admin_trend_windows,
    )
    return JsonResponse({"status_series": status_series})


@login_required
@group_required("ADMIN")
def admin_solicitantes(request):
    User = get_user_model()
    selected_raw = request.GET.get("solicitante", "").strip()
    selected_user = None

    solicitante_users = list(
        User.objects.filter(groups__name="SOLICITANTE").order_by(
            "first_name", "last_name", "username"
        )
    )

    if selected_raw.isdigit():
        selected_user = User.objects.filter(id=int(selected_raw)).first()
        if selected_user and selected_user not in solicitante_users:
            solicitante_users.insert(0, selected_user)

    selected_label = "Todos os solicitantes"
    selected_id = ""
    if selected_user:
        selected_label = selected_user.get_full_name() or selected_user.get_username()
        selected_id = str(selected_user.id)

    include_all = selected_user is None
    dashboard_user = selected_user or request.user

    solicitante_counts = _get_solicitante_status_counts(
        dashboard_user,
        include_all=include_all,
    )
    solicitante_extras = _get_solicitante_dashboard_extras(
        dashboard_user,
        include_all=include_all,
    )

    solicitante_options = [
        {
            "id": user.id,
            "label": user.get_full_name() or user.get_username(),
        }
        for user in solicitante_users
    ]

    context = {
        "selected_label": selected_label,
        "selected_solicitante_id": selected_id,
        "solicitante_options": solicitante_options,
        **solicitante_counts,
        **solicitante_extras,
    }

    return render(request, "portal/admin_solicitantes.html", context)

@login_required
@group_required("ADMIN")
def admin_projetistas(request):
    User = get_user_model()
    selected_raw = request.GET.get("projetista", "").strip()
    selected_user = None

    projetista_users = list(
        User.objects.filter(groups__name="PROJETISTA").order_by(
            "first_name", "last_name", "username"
        )
    )

    if selected_raw.isdigit():
        selected_user = User.objects.filter(id=int(selected_raw)).first()
        if selected_user and selected_user not in projetista_users:
            projetista_users.insert(0, selected_user)

    selected_label = "Todos os projetistas"
    selected_id = ""
    if selected_user:
        selected_label = selected_user.get_full_name() or selected_user.get_username()
        selected_id = str(selected_user.id)

    def _filter_solicitacoes_por_projetista(qs, user):
        candidate_fields = [
            "atribuido_para",
            "projetista",
            "designer",
            "responsavel",
            "assigned_to",
            "owner",
            "created_by",
            "user",
        ]
        for fname in candidate_fields:
            try:
                qs.model._meta.get_field(fname)
                return qs.filter(**{fname: user})
            except Exception:
                continue
        return qs.none()

    if selected_user:
        base_qs = _filter_solicitacoes_por_projetista(Solicitacao.objects.all(), selected_user)
    else:
        base_qs = Solicitacao.objects.all()

    pipeline_statuses = [
        SolicitacaoStatus.EM_FILA,
        SolicitacaoStatus.EM_PROJETO,
        SolicitacaoStatus.RETRABALHO,
        SolicitacaoStatus.AGUARDANDO_APROVACAO,
    ]
    active_qs = base_qs.filter(status__in=pipeline_statuses)
    fila_count = active_qs.filter(status=SolicitacaoStatus.EM_FILA).count()
    em_projeto_count = active_qs.filter(status=SolicitacaoStatus.EM_PROJETO).count()
    retrabalho_count = active_qs.filter(status=SolicitacaoStatus.RETRABALHO).count()
    prontos_count = active_qs.filter(status=SolicitacaoStatus.AGUARDANDO_APROVACAO).count()
    total_count = active_qs.count()

    def _pct(part, total):
        if total <= 0:
            return 0
        return int(round((part / total) * 100))

    sla_pct = _pct(total_count - retrabalho_count, total_count)
    fila_pct = _pct(fila_count, total_count)
    em_projeto_pct = _pct(em_projeto_count, total_count)
    retrabalho_pct = _pct(retrabalho_count, total_count)
    prontos_pct = _pct(prontos_count, total_count)

    projetistas_rows = []
    for user in projetista_users:
        user_qs = _filter_solicitacoes_por_projetista(Solicitacao.objects.all(), user)
        user_active = user_qs.filter(status__in=pipeline_statuses)
        user_fila = user_active.filter(status=SolicitacaoStatus.EM_FILA).count()
        user_em_projeto = user_active.filter(status=SolicitacaoStatus.EM_PROJETO).count()
        user_retrabalho = user_active.filter(status=SolicitacaoStatus.RETRABALHO).count()
        user_prontos = user_active.filter(status=SolicitacaoStatus.AGUARDANDO_APROVACAO).count()
        projetistas_rows.append(
            {
                "id": user.id,
                "name": user.get_full_name() or user.get_username(),
                "fila": user_fila,
                "em_projeto": user_em_projeto,
                "retrabalho": user_retrabalho,
                "prontos": user_prontos,
                "is_selected": bool(selected_user and user.id == selected_user.id),
            }
        )

    selected_solicitacoes = []
    if selected_user:
        selected_solicitacoes = [
            _decorate_solicitacao(sol)
            for sol in base_qs.select_related("criado_por", "atribuido_para")
            .order_by("-criado_em")[:60]
        ]

    projetista_options = [
        {
            "id": user.id,
            "label": user.get_full_name() or user.get_username(),
        }
        for user in projetista_users
    ]

    chart_entries = []
    now_local = timezone.localtime()
    chart_limit = 28
    chart_queryset = list(
        active_qs.select_related("criado_por", "atribuido_para")
        .order_by("criado_em")[:chart_limit]
    )
    gv_proj_map = _build_gv_proj_map(chart_queryset)
    for sol in chart_queryset:
        created = sol.criado_em
        if not created:
            continue
        created_local = timezone.localtime(created)
        age_seconds = (now_local - created_local).total_seconds()
        age_seconds = max(age_seconds, 0)
        age_days = age_seconds / 86400
        age_hours = age_seconds / 3600
        title = (sol.titulo or "").strip()
        if not title:
            title = "Solicitação sem título"
        if len(title) > 45:
            trimmed = title[:42].rstrip()
            title = f"{trimmed}..." if trimmed else "Solicitação"
        flow_label = (
            "Retrabalho"
            if sol.status == SolicitacaoStatus.RETRABALHO
            else "Retorno"
        )
        display_id = gv_proj_map.get(sol.id) or sol.job or f"#{sol.id}"
        created_label = created_local.strftime("%d/%m")
        label = f"{display_id} - {created_label}"
        chart_entries.append(
            {
                "id": sol.id,
                "display_id": display_id,
                "label": label,
                "created_at": created_local.isoformat(),
                "age_days": round(age_days, 2),
                "age_hours": round(age_hours, 2),
            }
        )

    context = {
        "selected_projetista": selected_user,
        "selected_label": selected_label,
        "selected_projetista_id": selected_id,
        "projetista_options": projetista_options,
        "projetistas_rows": projetistas_rows,
        "selected_solicitacoes": selected_solicitacoes,
        "total_count": total_count,
        "fila_count": fila_count,
        "em_projeto_count": em_projeto_count,
        "retrabalho_count": retrabalho_count,
        "prontos_count": prontos_count,
        "sla_pct": sla_pct,
        "fila_pct": fila_pct,
        "em_projeto_pct": em_projeto_pct,
        "retrabalho_pct": retrabalho_pct,
        "prontos_pct": prontos_pct,
        "projetista_chart_entries": chart_entries,
    }

    return render(request, "portal/admin_projetistas.html", context)

@login_required
@group_required("ADMIN")
def admin_dispositivos(request):
    selected_raw = request.GET.get("dispositivo", "").strip()

    base_all = Solicitacao.objects.exclude(numero_dispositivo__isnull=True).exclude(
        numero_dispositivo=""
    )

    dispositivos = list(
        base_all.values_list("numero_dispositivo", flat=True)
        .distinct()
        .order_by("numero_dispositivo")[:200]
    )

    selected_label = "Todos os dispositivos"
    selected_id = ""
    if selected_raw:
        selected_label = selected_raw
        selected_id = selected_raw
        base_qs = base_all.filter(numero_dispositivo=selected_raw)
    else:
        base_qs = base_all

    active_qs = base_qs.exclude(status=SolicitacaoStatus.CANCELADO)
    total_count = active_qs.count()
    validacao_count = active_qs.filter(status=SolicitacaoStatus.EM_PROJETO).count()
    liberacao_count = active_qs.filter(
        status=SolicitacaoStatus.AGUARDANDO_APROVACAO
    ).count()
    liberados_count = active_qs.filter(
        status__in=[SolicitacaoStatus.APROVADO, SolicitacaoStatus.CONCLUIDO]
    ).count()
    atraso_count = active_qs.filter(
        status__in=[SolicitacaoStatus.RETRABALHO, SolicitacaoStatus.REPROVADO]
    ).count()

    def _pct(part, total):
        if total <= 0:
            return 0
        return int(round((part / total) * 100))

    sla_pct = _pct(liberados_count, total_count)
    validacao_pct = _pct(validacao_count, total_count)
    liberacao_pct = _pct(liberacao_count, total_count)
    liberados_pct = _pct(liberados_count, total_count)
    atraso_pct = _pct(atraso_count, total_count)

    trend_lines = [
        {
            "key": "validacao",
            "label": "Validacao",
            "statuses": [SolicitacaoStatus.EM_PROJETO],
            "color": "#0b5f53",
        },
        {
            "key": "liberacao",
            "label": "Liberacao",
            "statuses": [SolicitacaoStatus.AGUARDANDO_APROVACAO],
            "color": "#2563eb",
        },
        {
            "key": "liberados",
            "label": "Liberados",
            "statuses": [SolicitacaoStatus.APROVADO, SolicitacaoStatus.CONCLUIDO],
            "color": "#16a34a",
        },
        {
            "key": "atraso",
            "label": "Atraso",
            "statuses": [SolicitacaoStatus.RETRABALHO, SolicitacaoStatus.REPROVADO],
            "color": "#dc2626",
        },
    ]
    trend_series = _build_status_time_series(
        queryset=base_qs,
        count=6,
        lines=trend_lines,
    )
    trend_period = trend_series.get("semana", [])
    trend_labels = [entry["label"] for entry in trend_period]
    trend_series_map = {
        line["key"]: [entry["counts"].get(line["key"], 0) for entry in trend_period]
        for line in trend_lines
    }
    trend_payload = {"labels": trend_labels, "series": trend_series_map}
    trend_lines_payload = [
        {"key": line["key"], "label": line["label"], "color": line["color"]}
        for line in trend_lines
    ]

    dispositivos_rows = []
    for numero in dispositivos:
        dev_qs = base_all.filter(numero_dispositivo=numero)
        dev_active = dev_qs.exclude(status=SolicitacaoStatus.CANCELADO)
        dev_total = dev_active.count()
        dev_validacao = dev_active.filter(status=SolicitacaoStatus.EM_PROJETO).count()
        dev_liberacao = dev_active.filter(
            status=SolicitacaoStatus.AGUARDANDO_APROVACAO
        ).count()
        dev_liberados = dev_active.filter(
            status__in=[SolicitacaoStatus.APROVADO, SolicitacaoStatus.CONCLUIDO]
        ).count()
        dev_atraso = dev_active.filter(
            status__in=[SolicitacaoStatus.RETRABALHO, SolicitacaoStatus.REPROVADO]
        ).count()
        dev_area = (
            dev_qs.exclude(area__isnull=True)
            .exclude(area="")
            .values_list("area", flat=True)
            .first()
            or "-"
        )
        dispositivos_rows.append(
            {
                "id": numero,
                "label": numero,
                "area": dev_area,
                "validacao": dev_validacao,
                "liberacao": dev_liberacao,
                "liberados": dev_liberados,
                "atraso": dev_atraso,
                "is_selected": bool(selected_raw and numero == selected_raw),
            }
        )

    selected_solicitacoes = []
    if selected_raw:
        selected_solicitacoes = [
            _decorate_solicitacao(sol)
            for sol in base_qs.select_related("criado_por", "atribuido_para")
            .order_by("-criado_em")[:60]
        ]

    dispositivo_options = [
        {
            "id": numero,
            "label": numero,
        }
        for numero in dispositivos
    ]

    context = {
        "selected_dispositivo": selected_raw or None,
        "selected_label": selected_label,
        "selected_dispositivo_id": selected_id,
        "dispositivo_options": dispositivo_options,
        "dispositivos_rows": dispositivos_rows,
        "selected_solicitacoes": selected_solicitacoes,
        "total_count": total_count,
        "validacao_count": validacao_count,
        "liberacao_count": liberacao_count,
        "liberados_count": liberados_count,
        "atraso_count": atraso_count,
        "sla_pct": sla_pct,
        "validacao_pct": validacao_pct,
        "liberacao_pct": liberacao_pct,
        "liberados_pct": liberados_pct,
        "atraso_pct": atraso_pct,
        "dispositivos_trend_payload": trend_payload,
        "dispositivos_trend_lines": trend_lines_payload,
    }

    return render(request, "portal/admin_dispositivos.html", context)

@login_required
@group_required("ADMIN")
def admin_banco_de_dados(request):
    User = get_user_model()
    action_msg = ""
    action_err = ""
    edit_solicitacao = None

    try:
        Solicitacao = apps.get_model("portal", "Solicitacao")
        SolicitacaoLog = apps.get_model("portal", "SolicitacaoLog")
    except LookupError:
        Solicitacao = None
        SolicitacaoLog = None

    status_values = {value for value, _ in SolicitacaoStatus.choices}
    priority_values = {int(value) for value, _ in Prioridade.choices}

    status_choices_json = json.dumps(
        [{"value": value, "label": label} for value, label in SolicitacaoStatus.choices],
        ensure_ascii=False,
    )
    priority_choices_json = json.dumps(
        [{"value": value, "label": label} for value, label in Prioridade.choices],
        ensure_ascii=False,
    )

    if request.method == "POST" and Solicitacao:
        action = request.POST.get("action", "").strip()
        if action == "inline_update":
            return _handle_inline_update(request, Solicitacao, status_values, priority_values)
        solicitacao_id_raw = request.POST.get("solicitacao_id", "").strip()
        if not solicitacao_id_raw.isdigit():
            action_err = "ID invalido."
        else:
            solicitacao = Solicitacao.objects.filter(id=int(solicitacao_id_raw)).first()
            if not solicitacao:
                action_err = "Solicitacao nao encontrada."
            elif action == "delete_solicitacao":
                solicitacao.delete()
                action_msg = f"Solicitacao #{solicitacao_id_raw} excluida."
            elif action == "update_solicitacao":
                old_status = solicitacao.status

                solicitacao.titulo = request.POST.get("titulo", "").strip()
                solicitacao.secao = request.POST.get("secao", "").strip()
                solicitacao.area = request.POST.get("area", "").strip()
                solicitacao.job = request.POST.get("job", "").strip()
                solicitacao.jobs_envolvidas = request.POST.get("jobs_envolvidas", "").strip()
                solicitacao.sufixo = request.POST.get("sufixo", "").strip()
                solicitacao.descricao_ferramenta = request.POST.get("descricao_ferramenta", "").strip()
                solicitacao.descricao = solicitacao.descricao_ferramenta
                solicitacao.wc = request.POST.get("wc", "").strip()
                solicitacao.quantidade = max(1, _parse_int(request.POST.get("quantidade", ""), solicitacao.quantidade or 1))
                solicitado_em = _parse_datetime(request.POST.get("solicitado_em", ""))
                if not solicitado_em:
                    solicitado_em = solicitacao.solicitado_em or timezone.now()
                solicitacao.solicitado_em = solicitado_em
                solicitacao.evento_sap = request.POST.get("evento_sap", "").strip()
                solicitacao.observacoes_projeto = request.POST.get("observacoes_projeto", "").strip()
                solicitacao.numero_moc = request.POST.get("numero_moc", "").strip()
                solicitacao.numero_dispositivo = request.POST.get("numero_dispositivo", "").strip()
                solicitacao.baseline_ame = _parse_date(request.POST.get("baseline_ame", ""))
                solicitacao.baseline_producao = _parse_date(request.POST.get("baseline_producao", ""))
                solicitacao.tipo_identificacao = request.POST.get("tipo_identificacao", "").strip()
                solicitacao.linha_produto = request.POST.get("linha_produto", "").strip()
                solicitacao.descricao_tecnica = request.POST.get("descricao_tecnica", "").strip()
                solicitacao.material = request.POST.get("material", "").strip()
                solicitacao.tratamento = request.POST.get("tratamento", "").strip()
                solicitacao.dim_criticas = request.POST.get("dim_criticas", "").strip()
                solicitacao.prazo_estimado = _parse_date(request.POST.get("prazo_estimado", ""))
                solicitacao.observacoes_aprovacao = request.POST.get("observacoes_aprovacao", "").strip()

                status_raw = request.POST.get("status", "").strip()
                if status_raw in status_values:
                    solicitacao.status = status_raw

                prioridade_raw = request.POST.get("prioridade", "").strip()
                if prioridade_raw.isdigit() and int(prioridade_raw) in priority_values:
                    solicitacao.prioridade = int(prioridade_raw)

                solicitacao.desenho_referencia = request.POST.get("desenho_referencia", "").strip()
                if request.FILES.get("anexos"):
                    solicitacao.anexos = request.FILES.get("anexos")

                solicitacao.save()

                if SolicitacaoLog and old_status != solicitacao.status:
                    SolicitacaoLog.objects.create(
                        solicitacao=solicitacao,
                        alterado_por=request.user,
                        status_de=old_status,
                        status_para=solicitacao.status,
                        comentario="Admin update",
                    )

                action_msg = f"Solicitacao #{solicitacao_id_raw} atualizada."
                edit_solicitacao = solicitacao

    group_filter = request.GET.get("group", "").strip()
    username_filter = request.GET.get("username", "").strip()
    status_filter = request.GET.get("status", "").strip()
    prioridade_filter = request.GET.get("prioridade", "").strip()
    q_filter = request.GET.get("q", "").strip()

    status_db_filter = status_filter if status_filter in status_values else ""
    screen_filter = status_filter if status_filter and status_filter not in status_values else ""
    screen_label = ""
    screen_url_name = ""
    group_screens = _ADMIN_SCREEN_OPTIONS.get(group_filter)
    if group_screens and screen_filter in group_screens:
        screen_label = group_screens[screen_filter]
        screen_url_name = screen_filter

    limit = 200
    limit_raw = request.GET.get("limit", "").strip()
    if limit_raw.isdigit():
        limit = max(1, min(int(limit_raw), 500))
    filters_query = urlencode(
        {
            key: value
            for key, value in {
                "group": group_filter,
                "username": username_filter,
                "status": status_filter,
                "prioridade": prioridade_filter,
                "q": q_filter,
                "limit": limit_raw if limit_raw.isdigit() else "",
            }.items()
            if value
        }
    )

    all_users_qs = User.objects.all().order_by("username").prefetch_related("groups")
    users_for_filter = []
    for user_item in all_users_qs:
        group_names = [g.name for g in user_item.groups.all()]
        users_for_filter.append(
            {
                "username": user_item.username,
                "groups_csv": ",".join(group_names),
            }
        )

    users_qs = all_users_qs
    if group_filter:
        users_qs = users_qs.filter(groups__name=group_filter)
    if username_filter:
        users_qs = users_qs.filter(username__icontains=username_filter)
    if q_filter:
        users_qs = users_qs.filter(
            Q(username__icontains=q_filter)
            | Q(first_name__icontains=q_filter)
            | Q(last_name__icontains=q_filter)
            | Q(email__icontains=q_filter)
        )

    users_total = users_qs.count()
    users = list(users_qs[:limit])

    solicitacoes = []
    logs = []
    solicitacoes_total = 0
    logs_total = 0

    if Solicitacao:
        sol_qs = Solicitacao.objects.select_related("criado_por", "atribuido_para").order_by("-criado_em")
        if status_db_filter:
            sol_qs = sol_qs.filter(status=status_db_filter)
        if prioridade_filter.isdigit():
            sol_qs = sol_qs.filter(prioridade=int(prioridade_filter))
        if username_filter:
            sol_qs = sol_qs.filter(
                Q(criado_por__username__icontains=username_filter)
                | Q(atribuido_para__username__icontains=username_filter)
            )
        if group_filter:
            sol_qs = sol_qs.filter(
                Q(criado_por__groups__name=group_filter)
                | Q(atribuido_para__groups__name=group_filter)
            )
        if q_filter:
            q_obj = Q(titulo__icontains=q_filter) | Q(descricao__icontains=q_filter)
            if q_filter.isdigit():
                q_obj = q_obj | Q(id=int(q_filter))
            sol_qs = sol_qs.filter(q_obj)

        solicitacoes_total = sol_qs.count()
        solicitacoes = list(sol_qs[:limit])
        gv_proj_map = _build_gv_proj_map(solicitacoes)
        for sol in solicitacoes:
            _decorate_solicitacao(sol, gv_proj_map)

    if SolicitacaoLog:
        log_qs = SolicitacaoLog.objects.select_related("solicitacao", "alterado_por").order_by("-criado_em")
        if status_db_filter:
            log_qs = log_qs.filter(Q(status_de=status_db_filter) | Q(status_para=status_db_filter))
        if username_filter:
            log_qs = log_qs.filter(alterado_por__username__icontains=username_filter)
        if group_filter:
            log_qs = log_qs.filter(alterado_por__groups__name=group_filter)
        if q_filter:
            q_obj = Q(comentario__icontains=q_filter) | Q(solicitacao__titulo__icontains=q_filter)
            if q_filter.isdigit():
                q_obj = q_obj | Q(solicitacao__id=int(q_filter)) | Q(id=int(q_filter))
            log_qs = log_qs.filter(q_obj)

        logs_total = log_qs.count()
        logs = list(log_qs[:limit])

    inline_rows = _build_inline_rows(solicitacoes)

    if not edit_solicitacao and Solicitacao:
        edit_id = request.GET.get("edit_id", "").strip()
        if edit_id.isdigit():
            edit_solicitacao = Solicitacao.objects.filter(id=int(edit_id)).first()
            if not edit_solicitacao and not action_err:
                action_err = "Solicitacao nao encontrada."

    db_config = settings.DATABASES.get("default", {})
    db_engine = str(db_config.get("ENGINE", "") or "")
    db_name = str(db_config.get("NAME", "") or "")
    db_name_display = Path(db_name).name if db_name else "-"
    db_status_ok = True
    db_error = ""
    try:
        connections["default"].ensure_connection()
    except Exception as exc:
        db_status_ok = False
        db_error = str(exc)
        if len(db_error) > 180:
            db_error = f"{db_error[:180]}..."

    if "sqlite" in db_engine:
        db_engine_label = "SQLite"
    elif "postgresql" in db_engine:
        db_engine_label = "PostgreSQL"
    elif "mysql" in db_engine:
        db_engine_label = "MySQL"
    elif db_engine:
        db_engine_label = db_engine.rsplit(".", 1)[-1]
    else:
        db_engine_label = "Database"

    context = {
        "users": users,
        "users_total": users_total,
        "solicitacoes": solicitacoes,
        "solicitacoes_total": solicitacoes_total,
        "logs": logs,
        "logs_total": logs_total,
        "db_engine_label": db_engine_label,
        "db_name_display": db_name_display,
        "db_status_ok": db_status_ok,
        "db_error": db_error,
        "filters": {
            "group": group_filter,
            "username": username_filter,
            "status": status_filter,
            "prioridade": prioridade_filter,
            "q": q_filter,
            "limit": limit,
        },
        "filters_query": filters_query,
        "screen_filter": screen_filter,
        "screen_label": screen_label,
        "screen_url_name": screen_url_name,
        "users_for_filter": users_for_filter,
        "group_options": ["ADMIN", "SOLICITANTE", "PROJETISTA", "DISPOSITIVOS"],
        "status_choices": SolicitacaoStatus.choices,
        "priority_choices": Prioridade.choices,
        "status_choices_json": status_choices_json,
        "priority_choices_json": priority_choices_json,
        "inline_fields": _INLINE_FIELD_CONFIG,
        "inline_rows": inline_rows,
        "edit_solicitacao": edit_solicitacao,
        "action_msg": action_msg,
        "action_err": action_err,
    }
    return render(request, "portal/admin_banco_de_dados.html", context)


# =========================
# ADMIN - USUARIOS / PERMISSOES
# =========================
@login_required
def admin_usuarios_permissoes(request):
    if not _is_admin_user(request.user):
        return redirect("portal_home")

    User = get_user_model()
    action_msg = ""
    action_err = ""
    selected_user_id = ""

    if request.method == "POST":
        selected_user_id = request.POST.get("user_id", "").strip()
        if not selected_user_id.isdigit():
            action_err = "Selecione um usuario valido."
        else:
            user = User.objects.filter(id=int(selected_user_id)).first()
            if not user:
                action_err = "Usuario nao encontrado."
            else:
                photo = request.FILES.get("photo")
                if not photo:
                    action_err = "Selecione uma foto para enviar."
                else:
                    profile, _ = UserProfile.objects.get_or_create(user=user)
                    profile.photo = photo
                    profile.save()
                    action_msg = f"Foto atualizada para {user.get_username()}."

    users = User.objects.order_by("first_name", "last_name", "username")

    directory_rows = [
        {
            "sso": entry["sso"],
            "name": entry["full_name"],
            "email": entry.get("email", ""),
            "profile_label": get_display_profile(entry["profile_key"]),
            "password": DEFAULT_PASSWORD_PLACEHOLDER,
        }
        for entry in USER_DIRECTORY
    ]

    context = {
        "users": users,
        "selected_user_id": selected_user_id,
        "action_msg": action_msg,
        "action_err": action_err,
        "directory_rows": directory_rows,
    }

    return render(request, "portal/admin_usuarios_permissoes.html", context)


# =========================
# ADMIN - AUDITORIA / LOGS
# =========================
@login_required
@group_required("ADMIN")
def admin_auditoria_logs(request):
    status_logs_qs = (
        SolicitacaoLog.objects.select_related("solicitacao", "alterado_por")
        .order_by("-criado_em")
    )
    audit_logs_qs = (
        AuditLog.objects.select_related("solicitacao", "usuario")
        .order_by("-criado_em")
    )
    search_query = (request.GET.get("q") or "").strip()
    user_query = (request.GET.get("user") or "").strip()
    status_query = (request.GET.get("status") or "").strip()
    action_query = (request.GET.get("acao") or "").strip()
    tipo_query = (request.GET.get("tipo") or "").strip().lower()

    if search_query:
        search_filter = (
            Q(solicitacao__titulo__icontains=search_query)
            | Q(solicitacao__numero_dispositivo__icontains=search_query)
            | Q(alterado_por__username__icontains=search_query)
            | Q(comentario__icontains=search_query)
        )
        if search_query.isdigit():
            search_filter |= Q(solicitacao__id=int(search_query))
        status_logs_qs = status_logs_qs.filter(search_filter)

        audit_filter = (
            Q(solicitacao__titulo__icontains=search_query)
            | Q(solicitacao__numero_dispositivo__icontains=search_query)
            | Q(usuario__username__icontains=search_query)
            | Q(descricao__icontains=search_query)
            | Q(acao__icontains=search_query)
        )
        if search_query.isdigit():
            audit_filter |= Q(solicitacao__id=int(search_query))
        audit_logs_qs = audit_logs_qs.filter(audit_filter)

    if user_query:
        status_logs_qs = status_logs_qs.filter(alterado_por__username__icontains=user_query)
        audit_logs_qs = audit_logs_qs.filter(
            Q(usuario__username__icontains=user_query)
            | Q(usuario__first_name__icontains=user_query)
            | Q(usuario__last_name__icontains=user_query)
        )

    status_values = {value for value, _ in SolicitacaoStatus.choices}
    if status_query in status_values:
        status_logs_qs = status_logs_qs.filter(
            Q(status_de=status_query) | Q(status_para=status_query)
        )

    if action_query:
        audit_logs_qs = audit_logs_qs.filter(acao__icontains=action_query)

    if tipo_query == "status":
        audit_logs_qs = audit_logs_qs.none()
    elif tipo_query == "acao":
        status_logs_qs = status_logs_qs.none()

    limit = _parse_int(request.GET.get("limit"), 200)
    limit = max(10, min(limit, 500))

    status_total = status_logs_qs.count()
    audit_total = audit_logs_qs.count()
    total_logs = status_total + audit_total

    status_logs = list(status_logs_qs[:limit])
    audit_logs = list(audit_logs_qs[:limit])

    rows = []
    for log in status_logs:
        rows.append(
            {
                "id": log.id,
                "criado_em": log.criado_em,
                "usuario": log.alterado_por,
                "solicitacao": log.solicitacao,
                "dispositivo": getattr(log.solicitacao, "numero_dispositivo", ""),
                "tipo": "STATUS",
                "acao_label": "Mudança de status",
                "status_de": log.status_de,
                "status_para": log.status_para,
                "comentario": log.comentario,
            }
        )
    for log in audit_logs:
        acao_label = AUDIT_ACTION_LABELS.get(log.acao, log.acao)
        rows.append(
            {
                "id": log.id,
                "criado_em": log.criado_em,
                "usuario": log.usuario,
                "solicitacao": log.solicitacao,
                "dispositivo": getattr(log.solicitacao, "numero_dispositivo", ""),
                "tipo": "AÇÃO",
                "acao_label": acao_label,
                "status_de": "",
                "status_para": "",
                "comentario": log.descricao,
            }
        )
    rows.sort(key=lambda item: item["criado_em"], reverse=True)
    logs = rows[:limit]

    status_labels = {value: label for value, label in SolicitacaoStatus.choices}
    context = {
        "logs": logs,
        "total_logs": total_logs,
        "display_limit": limit,
        "filters": {
            "q": search_query,
            "user": user_query,
            "status": status_query,
            "acao": action_query,
            "tipo": tipo_query,
            "limit": limit,
        },
        "status_options": SolicitacaoStatus.choices,
        "status_labels": status_labels,
        "filters_active": bool(search_query or user_query or status_query or action_query or tipo_query),
    }

    return render(request, "portal/admin_auditoria_logs.html", context)


# =========================
# CONFIGURACOES (USUARIO)
# =========================
@login_required
def configuracoes(request):
    user = request.user
    action_msg = ""
    action_err = ""

    if request.method == "POST":
        photo = request.FILES.get("photo")
        if not photo:
            action_err = "Selecione uma foto para enviar."
        else:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.photo = photo
            profile.save()
            action_msg = "Foto atualizada."

    group_label_map = {
        "ADMIN": "Admin",
        "SOLICITANTE": "Solicitante",
        "PROJETISTA": "Projetista",
        "DISPOSITIVOS": "Dispositivos",
    }
    group_names = list(user.groups.values_list("name", flat=True))
    group_labels = [group_label_map.get(name, name.title()) for name in group_names]

    is_admin = _is_admin_user(user)
    if is_admin and "Admin" not in group_labels:
        group_labels = ["Admin"] + group_labels

    sidebar_template = ""
    role_label = "Usuario"
    if is_admin:
        role_label = "Admin"
        sidebar_template = "portal/_sidebar_admin.html"
    elif in_group(user, "DISPOSITIVOS"):
        role_label = "Dispositivos"
        sidebar_template = "portal/_sidebar_dispositivos.html"
    elif in_group(user, "PROJETISTA"):
        role_label = "Projetista"
        sidebar_template = "portal/_sidebar_projetista.html"
    elif in_group(user, "SOLICITANTE"):
        role_label = "Solicitante"
        sidebar_template = "portal/_sidebar_solicitante.html"

    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = None

    username_value = user.get_username() or ""
    full_name_value = (user.get_full_name() or "").strip()
    display_name = full_name_value or username_value
    display_email = user.email or ""
    display_sso = ""

    directory_entry = find_directory_entry(
        username=username_value,
        full_name=full_name_value,
        email=display_email,
    )
    if directory_entry:
        directory_full_name = (directory_entry.get("full_name", "") or "").strip()
        if directory_full_name:
            if not full_name_value or len(directory_full_name.split()) > len(full_name_value.split()):
                display_name = directory_full_name
        if not display_email:
            display_email = directory_entry.get("email", "")
        display_sso = directory_entry.get("sso", "")

    if not display_sso and username_value.isdigit():
        display_sso = username_value
    if not display_email and "@" in username_value:
        display_email = username_value

    return render(
        request,
        "portal/configuracoes.html",
        {
            "action_msg": action_msg,
            "action_err": action_err,
            "group_labels": group_labels,
            "is_admin": is_admin,
            "profile": profile,
            "role_label": role_label,
            "sidebar_template": sidebar_template,
            "display_email": display_email,
            "display_name": display_name,
            "display_sso": display_sso,
        },
    )


# =========================
# NOTIFICACOES (RASCUNHO)
# =========================
def _format_notification_time(created_at, now=None):
    if not created_at:
        return ""
    local_now = timezone.localtime(now or timezone.now())
    local_created = timezone.localtime(created_at)
    delta = local_now - local_created
    if timedelta(0) <= delta <= timedelta(minutes=60):
        return "Agora"
    if local_created.date() == local_now.date():
        return local_created.strftime("Hoje %H:%M")
    if local_created.date() == (local_now - timedelta(days=1)).date():
        return local_created.strftime("Ontem %H:%M")
    return local_created.strftime("%d/%m/%Y")


def _format_date_br(value):
    if not value:
        return "-"
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%d/%m/%Y")


def _build_portal_url(name, params=None):
    base = reverse(name)
    if params:
        return f"{base}?{urlencode(params)}"
    return base


def _resolve_notification_shortcut(role, status):
    if role == "SOLICITANTE":
        if status in {SolicitacaoStatus.EM_FILA, SolicitacaoStatus.EM_PROJETO}:
            return (
                "Abrir controle de projetos (em andamento)",
                _build_portal_url(
                    "status_do_projeto", {"status": "aguardando_projetista"}
                ),
            )
        if status == SolicitacaoStatus.AGUARDANDO_APROVACAO:
            return (
                "Abrir controle de projetos (em aprovacao)",
                _build_portal_url(
                    "status_do_projeto", {"status": "aguardando_aprovacao"}
                ),
            )
        if status == SolicitacaoStatus.RETRABALHO:
            return (
                "Abrir controle de projetos (retrabalho)",
                _build_portal_url(
                    "status_do_projeto", {"status": "aguardando_retrabalho"}
                ),
            )
        if status == SolicitacaoStatus.APROVADO:
            return (
                "Abrir retorno final (aguardando retorno)",
                _build_portal_url("retorno_final", {"status": "retorno_final"}),
            )
        if status == SolicitacaoStatus.CONCLUIDO:
            return (
                "Abrir retorno final (concluidos)",
                _build_portal_url("retorno_final", {"status": "concluido"}),
            )
        if status == SolicitacaoStatus.CANCELADO:
            return (
                "Abrir retorno final (cancelados)",
                _build_portal_url("retorno_final", {"status": "cancelado"}),
            )
        if status == SolicitacaoStatus.REPROVADO:
            return (
                "Abrir solicitacoes reprovadas",
                _build_portal_url("solicitar_retrabalho"),
            )
        return ("", "")
    if role == "PROJETISTA":
        if status in {SolicitacaoStatus.EM_FILA, SolicitacaoStatus.EM_PROJETO}:
            return ("Abrir fila de trabalho", _build_portal_url("fila_trabalho"))
        if status == SolicitacaoStatus.RETRABALHO:
            return (
                "Abrir retrabalhos",
                _build_portal_url("retrabalho_solicitado"),
            )
        return ("", "")
    return ("", "")


_NOTIFICATION_CATEGORIES = {
    "todos": "Todas",
    "solicitante": "Solicitante",
    "projetista": "Projetista",
    "dispositivos": "Dispositivos",
    "admin": "Admin",
}


def _notification_status_label(status):
    meta = _STATUS_META.get(status)
    if meta:
        return meta["label"]
    return status


def _apply_notification_category(items, category_key):
    label = _NOTIFICATION_CATEGORIES.get(category_key, category_key.title())
    categorized = []
    for item in items:
        payload = dict(item)
        payload["category"] = category_key
        payload["category_label"] = label
        payload["id"] = f"{category_key}-{payload.get('id', '')}"
        categorized.append(payload)
    return categorized


def _notification_key(kind, obj_id, status=None, updated_at=None):
    if updated_at:
        stamp = updated_at.strftime("%Y%m%d%H%M%S%f")
    else:
        stamp = "0"
    status_token = status or "-"
    return f"{kind}:{obj_id}:{status_token}:{stamp}"


def _get_notifications_for_user(request):
    user = request.user
    if _is_admin_user(user):
        return "Admin", "portal/_sidebar_admin.html", _build_admin_notifications(request), True
    if in_group(user, "DISPOSITIVOS"):
        return (
            "Dispositivos",
            "portal/_sidebar_dispositivos.html",
            _build_dispositivos_notifications(request, viewer_is_admin=False),
            False,
        )
    if in_group(user, "PROJETISTA"):
        return (
            "Projetista",
            "portal/_sidebar_projetista.html",
            _build_projetista_notifications(request, user),
            False,
        )
    return (
        "Solicitante",
        "portal/_sidebar_solicitante.html",
        _build_solicitante_notifications(request, user),
        False,
    )


def _build_projetista_notification_item(request, solicitacao, gv_proj_map=None):
    solicitacao = _decorate_solicitacao(solicitacao, gv_proj_map=gv_proj_map)
    notif_ts = solicitacao.atualizado_em or solicitacao.criado_em
    notification_key = _notification_key(
        "projetista", solicitacao.id, solicitacao.status, notif_ts
    )
    solicitante = (
        solicitacao.criado_por.get_full_name()
        or solicitacao.criado_por.get_username()
    )
    solicitante_req = f"{solicitante} REQ"
    descricao = solicitacao.descricao_ferramenta or solicitacao.descricao or ""
    action_url = f"{reverse('preencher_solicitacao')}?{urlencode({'id': solicitacao.id})}"
    action_url_full = request.build_absolute_uri(action_url)
    shortcut_label, shortcut_url = _resolve_notification_shortcut(
        "PROJETISTA", solicitacao.status
    )

    email_payload = {
        "header": f"Solicitacao de Recurso Nº GV PROJ: {solicitacao.display_id}",
        "requester_line": f"{solicitante_req} Solicitou:",
        "rows": [
            {"label": "SO", "value": solicitacao.numero_moc or solicitacao.job or "-"},
            {
                "label": "Referencia p/ Aplicacao",
                "value": solicitacao.desenho_referencia or "-",
            },
            {
                "label": "Codigo do Recurso",
                "value": solicitacao.numero_dispositivo or "-",
            },
            {"label": "Descricao", "value": descricao or "-"},
            {"label": "Quantidade", "value": str(solicitacao.quantidade or 1)},
            {
                "label": "Data Devida Symix AME Projeto",
                "value": _format_date_br(solicitacao.baseline_ame),
            },
            {
                "label": "Data Devida Symix AME Entrega Kit",
                "value": _format_date_br(solicitacao.baseline_producao),
            },
            {"label": "Evento do SAP", "value": solicitacao.evento_sap or "-"},
            {"label": "Identificacao", "value": solicitacao.tipo_identificacao or "-"},
            {"label": "Linha Produto", "value": solicitacao.linha_produto or "-"},
        ],
        "comentarios": solicitacao.observacoes_projeto or "-",
        "link_label": "Acessar o Link Abaixo para Aprovar/Negar:",
        "action_url": action_url_full,
        "footer": "PLEASE DO NOT REPLY TO THIS SYSTEM GENERATED EMAIL.",
    }

    return {
        "id": solicitacao.id,
        "status": solicitacao.status,
        "key": notification_key,
        "title": f"Solicitacao de Recurso Nº GV PROJ: {solicitacao.display_id}",
        "preview": f"Nova solicitacao aberta por {solicitante}.",
        "meta": f"GV_PROJ {solicitacao.display_id} · Solicitante: {solicitante}",
        "time": _format_notification_time(notif_ts),
        "tag": "novo",
        "tag_label": "Novo",
        "body": "Nova solicitacao recebida. Verifique os detalhes abaixo.",
        "email": email_payload,
        "action_url": action_url,
        "action_label": "Abrir solicitacao",
        "shortcut_label": shortcut_label,
        "shortcut_url": shortcut_url,
    }


def _build_solicitante_notification_item(request, solicitacao, gv_proj_map=None):
    solicitacao = _decorate_solicitacao(solicitacao, gv_proj_map=gv_proj_map)
    notif_ts = solicitacao.atualizado_em or solicitacao.criado_em
    notification_key = _notification_key(
        "solicitante", solicitacao.id, solicitacao.status, notif_ts
    )
    projetista = "-"
    if solicitacao.atribuido_para:
        projetista = (
            solicitacao.atribuido_para.get_full_name()
            or solicitacao.atribuido_para.get_username()
        )
    descricao = solicitacao.descricao_ferramenta or solicitacao.descricao or ""
    disposicao_projetista = solicitacao.observacoes_aprovacao or ""
    if not disposicao_projetista:
        disposicao_projetista = "-"
    else:
        data_label = _format_date_br(solicitacao.atualizado_em)
        if projetista != "-":
            disposicao_projetista = f"{disposicao_projetista} - {projetista}"
        if data_label != "-":
            disposicao_projetista = f"{disposicao_projetista} - {data_label}"

    display_id = str(solicitacao.display_id or "")
    view_id = display_id if display_id.isdigit() else str(solicitacao.id)
    action_url = f"{reverse('status_do_projeto')}?{urlencode({'id': view_id, 'open': 1})}"
    action_url_full = request.build_absolute_uri(action_url)
    shortcut_label, shortcut_url = _resolve_notification_shortcut(
        "SOLICITANTE", solicitacao.status
    )

    status_label = solicitacao.status
    tag = "acao"
    tag_label = "Aprovar"
    if solicitacao.status == SolicitacaoStatus.AGUARDANDO_APROVACAO:
        status_label = "PROJETO LIBERADO PARA PROCESSISTA"
        tag = "acao"
        tag_label = "Aprovar"
    elif solicitacao.status == SolicitacaoStatus.RETRABALHO:
        status_label = "RETRABALHO SOLICITADO"
        tag = "revisar"
        tag_label = "Revisar"
    elif solicitacao.status == SolicitacaoStatus.APROVADO:
        status_label = "PROJETO APROVADO"
        tag = "final"
        tag_label = "Finalizar"
    elif solicitacao.status == SolicitacaoStatus.REPROVADO:
        status_label = "PROJETO REPROVADO"
        tag = "ajuste"
        tag_label = "Ajustar"
    elif solicitacao.status in {SolicitacaoStatus.EM_FILA, SolicitacaoStatus.EM_PROJETO}:
        status_label = "SOLICITACAO EM ANDAMENTO"
        tag = "check"
        tag_label = "Acompanhar"

    email_payload = {
        "header": f"Solicitacao de Recurso Nº GV PROJ: {solicitacao.display_id}",
        "requester_line": f"- {status_label}",
        "rows": [
            {"label": "SO", "value": solicitacao.numero_moc or solicitacao.job or "-"},
            {
                "label": "Referencia p/ Aplicacao",
                "value": solicitacao.desenho_referencia or "-",
            },
            {"label": "Ferramenta", "value": solicitacao.numero_dispositivo or "-"},
            {"label": "Descricao", "value": descricao or "-"},
            {"label": "Quantidade", "value": str(solicitacao.quantidade or 1)},
            {"label": "Disposicao Projetista", "value": disposicao_projetista},
            {"label": "Disposicao Processista", "value": "-"},
        ],
        "comentarios": "-",
        "link_label": "Acessar o Link Abaixo para Continuar:",
        "action_url": action_url_full,
        "footer": "PLEASE DO NOT REPLY TO THIS SYSTEM GENERATED EMAIL.",
    }

    return {
        "id": solicitacao.id,
        "status": solicitacao.status,
        "key": notification_key,
        "title": f"{status_label} - {solicitacao.display_id}",
        "preview": "Notificacao gerada automaticamente para acompanhamento.",
        "meta": f"GV_PROJ {solicitacao.display_id} - Projetista: {projetista}",
        "time": _format_notification_time(notif_ts),
        "tag": tag,
        "tag_label": tag_label,
        "body": "Revise os detalhes abaixo antes de prosseguir.",
        "email": email_payload,
        "action_url": action_url,
        "action_label": "Revisar solicitacao",
        "shortcut_label": shortcut_label,
        "shortcut_url": shortcut_url,
    }


def _build_dispositivos_notification_item(
    request,
    solicitacao,
    gv_proj_map=None,
    viewer_is_admin=False,
):
    solicitacao = _decorate_solicitacao(solicitacao, gv_proj_map=gv_proj_map)
    notif_ts = solicitacao.atualizado_em or solicitacao.criado_em
    notification_key = _notification_key(
        "dispositivos", solicitacao.id, solicitacao.status, notif_ts
    )
    solicitante = (
        solicitacao.criado_por.get_full_name()
        or solicitacao.criado_por.get_username()
    )
    projetista = "-"
    if solicitacao.atribuido_para:
        projetista = (
            solicitacao.atribuido_para.get_full_name()
            or solicitacao.atribuido_para.get_username()
        )
    dispositivo = solicitacao.numero_dispositivo or "-"
    status_label = _notification_status_label(solicitacao.status)

    tag = "acao"
    tag_label = "Acompanhar"
    if solicitacao.status == SolicitacaoStatus.AGUARDANDO_APROVACAO:
        tag = "check"
        tag_label = "Validar"
    elif solicitacao.status == SolicitacaoStatus.RETRABALHO:
        tag = "ajuste"
        tag_label = "Retrabalho"
    elif solicitacao.status in {SolicitacaoStatus.APROVADO, SolicitacaoStatus.CONCLUIDO}:
        tag = "final"
        tag_label = "Liberado"
    elif solicitacao.status == SolicitacaoStatus.CANCELADO:
        tag = "admin"
        tag_label = "Cancelado"
    elif solicitacao.status == SolicitacaoStatus.REPROVADO:
        tag = "ajuste"
        tag_label = "Reprovado"

    if viewer_is_admin and dispositivo != "-":
        action_url = f"{reverse('admin_dispositivos')}?{urlencode({'dispositivo': dispositivo})}"
        action_label = "Abrir painel de dispositivos"
    else:
        action_url = reverse("dispositivos_dashboard")
        action_label = "Abrir painel de dispositivos"

    return {
        "id": solicitacao.id,
        "status": solicitacao.status,
        "key": notification_key,
        "title": f"Dispositivo {dispositivo} · {solicitacao.display_id}",
        "preview": f"{status_label} para o dispositivo {dispositivo}.",
        "meta": (
            f"GV_PROJ {solicitacao.display_id} · Solicitante: {solicitante} "
            f"· Projetista: {projetista}"
        ),
        "time": _format_notification_time(notif_ts),
        "tag": tag,
        "tag_label": tag_label,
        "body": (
            "Acompanhe o ciclo do dispositivo e verifique pendencias associadas."
        ),
        "action_url": action_url,
        "action_label": action_label,
    }


def _build_admin_log_notifications(request, limit=60):
    logs = list(
        SolicitacaoLog.objects.select_related("solicitacao", "alterado_por")[:limit]
    )
    if not logs:
        return []
    solicitacoes = [log.solicitacao for log in logs if log.solicitacao_id]
    gv_proj_map = _build_gv_proj_map(solicitacoes)
    items = []
    for log in logs:
        solicitacao = log.solicitacao
        if not solicitacao:
            continue
        notification_key = _notification_key(
            "adminlog", log.id, log.status_para, log.criado_em
        )
        solicitacao = _decorate_solicitacao(solicitacao, gv_proj_map=gv_proj_map)
        display_id = str(solicitacao.display_id or "")
        view_id = display_id if display_id.isdigit() else str(solicitacao.id)
        status_from = _notification_status_label(log.status_de)
        status_to = _notification_status_label(log.status_para)
        actor = log.alterado_por.get_full_name() or log.alterado_por.get_username()
        action_url = f"{reverse('status_do_projeto')}?{urlencode({'id': view_id, 'open': 1})}"
        items.append(
            {
                "id": log.id,
                "status": log.status_para,
                "key": notification_key,
                "title": f"Status atualizado: GV_PROJ {display_id}",
                "preview": f"{status_from} -> {status_to}",
                "meta": f"Admin · Alterado por {actor}",
                "time": _format_notification_time(log.criado_em),
                "tag": "admin",
                "tag_label": "Log",
                "body": (
                    f"Solicitacao {display_id} mudou de {status_from} para {status_to}."
                ),
                "action_url": action_url,
                "action_label": "Abrir solicitacao",
            }
        )
    return items


def _build_dispositivos_notifications(request, viewer_is_admin=False):
    solicitacoes_raw = list(
        Solicitacao.objects.exclude(numero_dispositivo__isnull=True)
        .exclude(numero_dispositivo="")
        .exclude(status=SolicitacaoStatus.RASCUNHO)
        .select_related("criado_por", "atribuido_para")
        .order_by("-atualizado_em")[:120]
    )
    if not solicitacoes_raw:
        return []
    gv_proj_map = _build_gv_proj_map(solicitacoes_raw)
    return [
        _build_dispositivos_notification_item(
            request,
            solicitacao,
            gv_proj_map=gv_proj_map,
            viewer_is_admin=viewer_is_admin,
        )
        for solicitacao in solicitacoes_raw
    ]


def _build_admin_notifications(request):
    solicitante_items = list(
        Solicitacao.objects.exclude(status=SolicitacaoStatus.RASCUNHO)
        .select_related("criado_por", "atribuido_para")
        .order_by("-atualizado_em")[:120]
    )
    projetista_items = list(
        Solicitacao.objects.filter(
            status__in=[
                SolicitacaoStatus.EM_FILA,
                SolicitacaoStatus.EM_PROJETO,
                SolicitacaoStatus.RETRABALHO,
            ]
        )
        .select_related("criado_por", "atribuido_para")
        .order_by("-criado_em")[:120]
    )

    items = []
    if solicitante_items:
        gv_proj_map = _build_gv_proj_map(solicitante_items)
        items.extend(
            _apply_notification_category(
                [
                    _build_solicitante_notification_item(
                        request, solicitacao, gv_proj_map=gv_proj_map
                    )
                    for solicitacao in solicitante_items
                ],
                "solicitante",
            )
        )
    if projetista_items:
        gv_proj_map = _build_gv_proj_map(projetista_items)
        items.extend(
            _apply_notification_category(
                [
                    _build_projetista_notification_item(
                        request, solicitacao, gv_proj_map=gv_proj_map
                    )
                    for solicitacao in projetista_items
                ],
                "projetista",
            )
        )

    dispositivos_items = _build_dispositivos_notifications(request, viewer_is_admin=True)
    if dispositivos_items:
        items.extend(_apply_notification_category(dispositivos_items, "dispositivos"))

    admin_logs = _build_admin_log_notifications(request)
    if admin_logs:
        items.extend(_apply_notification_category(admin_logs, "admin"))
    return items


def _build_projetista_notifications(request, user):
    solicitacoes_raw = list(
        Solicitacao.objects.filter(
            status__in=[
                SolicitacaoStatus.EM_FILA,
                SolicitacaoStatus.EM_PROJETO,
                SolicitacaoStatus.RETRABALHO,
            ],
        )
        .filter(Q(atribuido_para=user) | Q(atribuido_para__isnull=True))
        .select_related("criado_por", "atribuido_para")
        .order_by("-criado_em")[:120]
    )
    if not solicitacoes_raw:
        return []
    gv_proj_map = _build_gv_proj_map(solicitacoes_raw)
    return [
        _build_projetista_notification_item(
            request, solicitacao, gv_proj_map=gv_proj_map
        )
        for solicitacao in solicitacoes_raw
    ]


def _build_solicitante_notifications(request, user):
    solicitacoes_raw = list(
        Solicitacao.objects.filter(
            criado_por=user,
        )
        .exclude(status=SolicitacaoStatus.RASCUNHO)
        .select_related("criado_por", "atribuido_para")
        .order_by("-atualizado_em")[:120]
    )
    if not solicitacoes_raw:
        return []
    gv_proj_map = _build_gv_proj_map(solicitacoes_raw)
    return [
        _build_solicitante_notification_item(
            request, solicitacao, gv_proj_map=gv_proj_map
        )
        for solicitacao in solicitacoes_raw
    ]


@login_required
def notificacoes(request):
    user = request.user
    role_label, sidebar_template, base_items, is_admin = _get_notifications_for_user(
        request
    )
    base_items = list(base_items)

    category_filters = []
    active_category = {"key": "todos", "label": "Todas"}
    if is_admin:
        category_filter = request.GET.get("category", "").strip().lower() or "todos"
        if category_filter not in _NOTIFICATION_CATEGORIES:
            category_filter = "todos"
        for key, label in _NOTIFICATION_CATEGORIES.items():
            category_filters.append(
                {
                    "key": key,
                    "label": label,
                    "count": sum(
                        1
                        for item in base_items
                        if key == "todos" or item.get("category") == key
                    ),
                    "active": category_filter == key,
                }
            )
        active_category = next(
            (group for group in category_filters if group.get("active")),
            category_filters[0] if category_filters else active_category,
        )
    else:
        category_filter = "todos"

    filter_base_items = base_items
    if is_admin and category_filter != "todos":
        filter_base_items = [
            item for item in base_items if item.get("category") == category_filter
        ]

    status_groups = [
        {
            "key": "pendente",
            "label": "Pendente",
            "statuses": {SolicitacaoStatus.EM_FILA, SolicitacaoStatus.EM_PROJETO},
        },
        {
            "key": "aprovacao",
            "label": "Em aprovacao",
            "statuses": {SolicitacaoStatus.AGUARDANDO_APROVACAO},
        },
        {"key": "retrabalho", "label": "Retrabalho", "statuses": {SolicitacaoStatus.RETRABALHO}},
        {
            "key": "aprovado",
            "label": "Aprovado",
            "statuses": {SolicitacaoStatus.APROVADO, SolicitacaoStatus.CONCLUIDO},
        },
        {"key": "cancelado", "label": "Cancelado", "statuses": {SolicitacaoStatus.CANCELADO}},
    ]
    status_map = {group["key"]: group for group in status_groups}
    status_filter = request.GET.get("status", "").strip().lower() or "pendente"
    if status_filter not in status_map:
        status_filter = "pendente"

    items = [
        item
        for item in filter_base_items
        if item.get("status") in status_map[status_filter]["statuses"]
    ]

    selected_id = request.GET.get("id", "").strip()
    selected = items[0] if items else None
    if selected_id:
        for item in items:
            if str(item.get("id")) == selected_id:
                selected = item
                break

    for item in base_items:
        item["unread"] = True
    notifications_count = len(base_items)

    filters = []
    for group in status_groups:
        filters.append(
            {
                "key": group["key"],
                "label": group["label"],
                "count": sum(
                    1
                    for item in filter_base_items
                    if item.get("status") in group["statuses"]
                ),
                "active": status_filter == group["key"],
            }
        )
    active_filter = next(
        (group for group in filters if group.get("active")), filters[0]
    )

    return render(
        request,
        "portal/notificacoes.html",
        {
            "role_label": role_label,
            "sidebar_template": sidebar_template,
            "notifications": items,
            "selected": selected,
            "filters": filters,
            "active_filter": active_filter,
            "notifications_count": notifications_count,
            "category_filters": category_filters,
            "active_category": active_category,
        },
    )


# =========================
# SOLICITANTE
# =========================
@login_required
@group_required("SOLICITANTE")
def solicitante_dashboard(request):
    counts = _get_solicitante_status_counts(request.user, include_all=False)
    admin_mode = _is_admin_user(request.user)
    extras = _get_solicitante_dashboard_extras(request.user, include_all=admin_mode)

    return render(
        request,
        "portal/solicitante_dashboard.html",
        {
            **counts,
            "admin_mode": admin_mode,
            **extras,
        },
    )


@login_required
def novo_apontamento(request):
    admin_mode = _require_group_or_admin(request, "SOLICITANTE")
    ok = False
    ok_message = ""
    form_error = False
    solicitacao = None
    User = get_user_model()
    edit_mode = False

    solicitacao_id = request.GET.get("id") or request.POST.get("solicitacao_id")
    if solicitacao_id and str(solicitacao_id).isdigit():
        if admin_mode:
            solicitacao = get_object_or_404(Solicitacao, id=int(solicitacao_id))
        else:
            solicitacao = get_object_or_404(
                Solicitacao, id=int(solicitacao_id), criado_por=request.user
            )
        edit_mode = True
    elif admin_mode:
        return redirect("admin_banco_de_dados")

    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        if action == "delete" and solicitacao:
            if admin_mode or solicitacao.criado_por_id == request.user.id:
                log_action(
                    request,
                    "solicitante_excluir_solicitacao",
                    solicitacao=solicitacao,
                    descricao="Solicitação excluída.",
                    extra={"admin_mode": admin_mode},
                )
                solicitacao.delete()
                if admin_mode:
                    return redirect("admin_banco_de_dados")
                return redirect("status_do_projeto")
            raise PermissionDenied

        required_fields = {
            "job": "JOB",
            "descricao_ferramenta": "Descricao da Ferramenta",
            "desenho_referencia": "Desenho de referencia",
            "wc": "WC",
            "solicitado_em": "Data da Solicitacao",
            "area": "Area",
            "jobs_envolvidas": "JOBs Envolvidas",
            "sufixo": "Sufixo",
            "quantidade": "Qtd.",
            "evento_sap": "Evento SAP",
            "numero_moc": "Numero do MOC",
            "numero_dispositivo": "No do Dispositivo",
            "baseline_ame": "Data Baseline AME Projeto",
            "baseline_producao": "Data Baseline Producao Entrega Kit",
        }
        missing = [
            label for field, label in required_fields.items()
            if not request.POST.get(field, "").strip()
        ]

        if missing:
            ok = False
            form_error = True
            ok_message = "Preencha todos os campos obrigatorios (exceto Observacoes para o Projeto)."
        else:
            secao = request.POST.get("secao", "").strip()
            job = request.POST.get("job", "").strip()
            area = request.POST.get("area", "").strip()
            numero_moc = request.POST.get("numero_moc", "").strip()
            if not secao:
                secao = area
            titulo = job or secao or area or "Solicitacao"
            if numero_moc and not job:
                titulo = f"MOC {numero_moc}"

            quantidade_raw = _parse_int(request.POST.get("quantidade", ""), 1)
            quantidade = max(1, quantidade_raw)
            sufixo = request.POST.get("sufixo", "").strip()
            descricao_ferramenta = request.POST.get("descricao_ferramenta", "").strip()
            desenho_referencia = request.POST.get("desenho_referencia", "").strip()

            if solicitacao:
                solicitacao.titulo = titulo
                solicitacao.secao = secao
                solicitacao.job = job
                solicitacao.area = area
                solicitacao.jobs_envolvidas = request.POST.get("jobs_envolvidas", "").strip()
                solicitacao.sufixo = sufixo
                solicitacao.descricao_ferramenta = descricao_ferramenta
                solicitacao.descricao = descricao_ferramenta
                solicitacao.desenho_referencia = desenho_referencia
                solicitacao.wc = request.POST.get("wc", "").strip()
                solicitacao.quantidade = quantidade
                solicitado_em = _parse_datetime(request.POST.get("solicitado_em", ""))
                if not solicitado_em:
                    solicitado_em = solicitacao.solicitado_em or timezone.now()
                solicitacao.solicitado_em = solicitado_em
                solicitacao.evento_sap = request.POST.get("evento_sap", "").strip()
                solicitacao.observacoes_projeto = request.POST.get("observacoes_projeto", "").strip()
                solicitacao.numero_moc = numero_moc
                solicitacao.numero_dispositivo = request.POST.get("numero_dispositivo", "").strip()
                solicitacao.baseline_ame = _parse_date(request.POST.get("baseline_ame", ""))
                solicitacao.baseline_producao = _parse_date(request.POST.get("baseline_producao", ""))
                solicitacao.tipo_identificacao = request.POST.get("tipo_identificacao", "").strip()
                solicitacao.linha_produto = request.POST.get("linha_produto", "").strip()

                status_raw = request.POST.get("status", "").strip()
                if not admin_mode and status_raw in {"ENVIAR", "EM_ESPERA"}:
                    solicitacao.status = SolicitacaoStatus.EM_FILA

                if solicitacao.atribuido_para_id is None and sufixo:
                    solicitacao.atribuido_para = _resolve_projetista_user(User, sufixo)

                solicitacao.save()
                log_action(
                    request,
                    "solicitante_editar_solicitacao",
                    solicitacao=solicitacao,
                    descricao="Solicitação atualizada.",
                    extra={"admin_mode": admin_mode, "status": solicitacao.status},
                )
                if not admin_mode:
                    return redirect("status_do_projeto")
                ok = True
                ok_message = "Solicitacao atualizada."
            else:
                status = SolicitacaoStatus.EM_FILA

                atribuido_para = _resolve_projetista_user(User, sufixo)

                solicitacao = Solicitacao.objects.create(
                    titulo=titulo,
                    descricao=descricao_ferramenta,
                    status=status,
                    criado_por=request.user,
                    atribuido_para=atribuido_para,
                    secao=secao,
                    job=job,
                    jobs_envolvidas=request.POST.get("jobs_envolvidas", "").strip(),
                    sufixo=sufixo,
                    descricao_ferramenta=descricao_ferramenta,
                    desenho_referencia=desenho_referencia,
                    wc=request.POST.get("wc", "").strip(),
                    quantidade=quantidade,
                    solicitado_em=_parse_datetime(request.POST.get("solicitado_em", "")) or timezone.now(),
                    evento_sap=request.POST.get("evento_sap", "").strip(),
                    observacoes_projeto=request.POST.get("observacoes_projeto", "").strip(),
                    numero_moc=numero_moc,
                    numero_dispositivo=request.POST.get("numero_dispositivo", "").strip(),
                    area=area,
                    baseline_ame=_parse_date(request.POST.get("baseline_ame", "")),
                    baseline_producao=_parse_date(request.POST.get("baseline_producao", "")),
                    tipo_identificacao=request.POST.get("tipo_identificacao", "").strip(),
                    linha_produto=request.POST.get("linha_produto", "").strip(),
                )
                log_action(
                    request,
                    "solicitante_criar_solicitacao",
                    solicitacao=solicitacao,
                    descricao="Solicitação criada e enviada para a fila do projetista.",
                    extra={"status": solicitacao.status},
                )
                ok = True
                ok_message = "Solicitacao salva e enviada para a fila do projetista."

    return render(
        request,
        "portal/novo_apontamento.html",
        {
            "ok": ok,
            "ok_message": ok_message,
            "form_error": form_error,
            "solicitacao": solicitacao,
            "admin_mode": admin_mode,
            "edit_mode": edit_mode,
            "solicitado_em_default": timezone.localtime(),
        },
    )


@login_required
def tabela_consulta(request):
    return render(request, "portal/tabela_consulta.html")


@login_required
def registro_placeholder(request):
    return render(request, "portal/registro_placeholder.html")


@login_required
def pagina_placeholder(request):
    return render(request, "portal/pagina_placeholder.html")


@login_required
def status_do_projeto(request):
    admin_mode = _require_group_or_admin(request, "SOLICITANTE")
    solicitacao_id = request.GET.get("id", "").strip()
    status_filter = request.GET.get("status", "").strip()
    q_filter = request.GET.get("q", "").strip()
    back_target = request.GET.get("back", "").strip()

    qs = Solicitacao.objects.select_related("criado_por", "atribuido_para").order_by("-criado_em")
    if not admin_mode:
        qs = qs.filter(criado_por=request.user)
    qs = qs.exclude(status__in=_FINAL_STATUS_VALUES)

    if solicitacao_id.isdigit():
        gv_match = _resolve_gv_proj_to_solicitacao_id(solicitacao_id)
        if gv_match:
            qs = qs.filter(id=gv_match)
        else:
            qs = qs.filter(id=int(solicitacao_id))

    if status_filter in _STATUS_FILTER_MAP:
        qs = qs.filter(status__in=_STATUS_FILTER_MAP[status_filter])

    qs = _apply_q_filter(qs, q_filter)

    solicitacoes_raw = list(qs[:200])
    gv_proj_map = _build_gv_proj_map(solicitacoes_raw)
    solicitacoes = [_decorate_solicitacao(sol, gv_proj_map=gv_proj_map) for sol in solicitacoes_raw]
    pendentes_count = qs.count()

    status_filters = [
        {"value": key, "label": label}
        for key, label, _ in _STATUS_FILTER_OPTIONS
        if key not in _FINAL_STATUS_KEYS
    ]
    active_status_label = "Todos"
    for key, label, _ in _STATUS_FILTER_OPTIONS:
        if key == status_filter:
            active_status_label = label
            break

    back_url = ""
    if back_target == "aprovar_reaprovar":
        back_url = reverse("aprovar_reaprovar")
        params = {}
        if q_filter:
            params["q"] = q_filter
        if params:
            back_url = f"{back_url}?{urlencode(params)}"

    context = {
        "admin_mode": admin_mode,
        "solicitacoes": solicitacoes,
        "status_filters": status_filters,
        "active_status_label": active_status_label,
        "filters": {
            "status": status_filter,
            "q": q_filter,
        },
        "back_url": back_url,
    }
    return render(request, "portal/status_do_projeto.html", context)


@login_required
def status_finalizadas(request):
    admin_mode = _require_group_or_admin(request, "SOLICITANTE")
    solicitacao_id = request.GET.get("id", "").strip()

    qs = Solicitacao.objects.select_related("criado_por", "atribuido_para").order_by("-criado_em")
    if not admin_mode:
        qs = qs.filter(criado_por=request.user)

    if solicitacao_id.isdigit():
        gv_match = _resolve_gv_proj_to_solicitacao_id(solicitacao_id)
        if gv_match:
            qs = qs.filter(id=gv_match)
        else:
            qs = qs.filter(id=int(solicitacao_id))

    qs = qs.filter(status__in=_FINAL_STATUS_VALUES)

    solicitacoes_raw = list(qs[:200])
    gv_proj_map = _build_gv_proj_map(solicitacoes_raw)
    solicitacoes = [_decorate_solicitacao(sol, gv_proj_map=gv_proj_map) for sol in solicitacoes_raw]

    context = {
        "admin_mode": admin_mode,
        "solicitacoes": solicitacoes,
    }
    return render(request, "portal/status_finalizadas.html", context)


@login_required
def buscar_solicitacao(request):
    admin_mode = _require_group_or_admin(request, "SOLICITANTE")
    query = request.GET.get("q", "").strip()
    redirect_mode = request.GET.get("redirect") == "1"
    if not query:
        if redirect_mode:
            return redirect("status_do_projeto")
        return JsonResponse({"items": []})

    ids = re.findall(r"\d+", query)
    if not ids:
        if redirect_mode:
            return redirect("status_do_projeto")
        return JsonResponse({"items": []})

    solicitacao_id_raw = ids[-1]
    solicitacao_id = _resolve_gv_proj_to_solicitacao_id(solicitacao_id_raw)
    if solicitacao_id is None:
        solicitacao_id = int(solicitacao_id_raw)
    qs = Solicitacao.objects.select_related("criado_por", "atribuido_para").filter(
        id=solicitacao_id
    )
    if not admin_mode:
        qs = qs.filter(criado_por=request.user)

    solicitacao = qs.first()
    if not solicitacao:
        if redirect_mode:
            fallback_url = f"{reverse('status_do_projeto')}?{urlencode({'id': solicitacao_id_raw, 'open': 1})}"
            return redirect(fallback_url)
        return JsonResponse({"items": []})

    solicitacao = _decorate_solicitacao(solicitacao)
    display_id = str(solicitacao.display_id or "")
    view_id = display_id if display_id.isdigit() else str(solicitacao.id)
    target_view = "status_do_projeto"
    action_label = "Controle de projetos"
    if solicitacao.status in {SolicitacaoStatus.APROVADO, SolicitacaoStatus.CANCELADO}:
        target_view = "retorno_final"
        action_label = "Retorno final"
    elif solicitacao.status in _FINAL_STATUS_VALUES:
        target_view = "status_finalizadas"
        action_label = "Finalizadas"

    action_url = f"{reverse(target_view)}?{urlencode({'id': view_id, 'open': 1})}"

    if solicitacao.atribuido_para:
        projetista = (
            solicitacao.atribuido_para.get_full_name()
            or solicitacao.atribuido_para.get_username()
        )
    else:
        projetista = "-"

    item = {
        "id": solicitacao.id,
        "display_id": solicitacao.display_id,
        "titulo": solicitacao.titulo or "Solicitacao",
        "status_label": solicitacao.status_label,
        "status_key": solicitacao.status_key,
        "criado_em": solicitacao.criado_em.strftime("%Y-%m-%d"),
        "projetista": projetista,
        "action_label": action_label,
        "action_url": action_url,
    }
    if redirect_mode:
        return redirect(action_url)
    return JsonResponse({"items": [item]})


@login_required
def buscar_descricao_dispositivo(request):
    codigo_raw = request.GET.get("codigo", "").strip()
    if not codigo_raw:
        return JsonResponse({"descricao": ""})

    codigo = _normalize_codigo_dispositivo(codigo_raw)
    if not codigo:
        return JsonResponse({"descricao": ""})

    try:
        DispositivoCatalogo = apps.get_model("portal", "DispositivoCatalogo")
    except LookupError:
        return JsonResponse({"descricao": ""})

    item = DispositivoCatalogo.objects.filter(codigo=codigo).first()
    return JsonResponse({"descricao": item.descricao if item else ""})


@login_required
def aprovar_reaprovar(request):
    admin_mode = _require_group_or_admin(request, "SOLICITANTE")
    ok = False
    action_msg = ""
    action_err = ""
    comentario = ""
    selected_id = ""
    q_filter = request.GET.get("q", "").strip()

    qs = Solicitacao.objects.select_related("criado_por", "atribuido_para").filter(
        status=SolicitacaoStatus.AGUARDANDO_APROVACAO
    )
    if not admin_mode:
        qs = qs.filter(criado_por=request.user)
    qs = _apply_q_filter(qs, q_filter)

    if request.method == "POST":
        selected_id = request.POST.get("solicitacao_id", "").strip()
        acao = request.POST.get("acao", "").strip()
        comentario = request.POST.get("comentario", "").strip()

        if not selected_id.isdigit():
            action_err = "Selecione uma solicitacao valida."
        else:
            solicitacao = qs.filter(id=int(selected_id)).first()
            if not solicitacao:
                action_err = "Solicitacao nao encontrada."
            elif acao not in {"aprovar", "reprovar"}:
                action_err = "Acao invalida."
            else:
                novo_status = (
                    SolicitacaoStatus.APROVADO
                    if acao == "aprovar"
                    else SolicitacaoStatus.REPROVADO
                )
                solicitacao.mudar_status(novo_status, request.user, comentario=comentario)
                ok = True
                if acao == "aprovar":
                    action_msg = "Solicitacao aprovada."
                else:
                    action_msg = "Solicitacao reprovada. Disponivel para solicitar retrabalho."
                qs = qs.exclude(id=solicitacao.id)

    solicitacoes = [_decorate_solicitacao(sol) for sol in qs[:200]]
    pendentes_count = qs.count()
    if not selected_id and request.GET.get("id", "").isdigit():
        selected_id = request.GET.get("id", "").strip()

    return render(
        request,
        "portal/aprovar_reaprovar.html",
        {
            "ok": ok,
            "action_msg": action_msg,
            "action_err": action_err,
            "comentario": comentario,
            "solicitacoes": solicitacoes,
            "selected_id": selected_id,
            "admin_mode": admin_mode,
            "pendentes_count": pendentes_count,
            "filters": {"q": q_filter},
        },
    )
    if request.method == "POST":
        ok = True
    return render(request, "portal/aprovar_reaprovar.html", {"ok": ok, "admin_mode": admin_mode})


@login_required
def solicitar_retrabalho(request):
    admin_mode = _require_group_or_admin(request, "SOLICITANTE")
    ok = False
    action_msg = ""
    action_err = ""
    motivo = ""
    selected_id = ""
    q_filter = request.GET.get("q", "").strip()

    qs = Solicitacao.objects.select_related("criado_por", "atribuido_para").filter(
        status=SolicitacaoStatus.REPROVADO
    )
    if not admin_mode:
        qs = qs.filter(criado_por=request.user)
    qs = _apply_q_filter(qs, q_filter)

    if request.method == "POST":
        selected_id = request.POST.get("solicitacao_id", "").strip()
        motivo = request.POST.get("motivo", "").strip()
        prazo_raw = request.POST.get("prazo_desejado", "").strip()
        anexos = request.FILES.get("anexo")

        checklist = []
        if request.POST.get("check_dimensoes"):
            checklist.append("ajustar_dimensoes")
        if request.POST.get("check_desenho"):
            checklist.append("corrigir_desenho")
        if request.POST.get("check_evidencia"):
            checklist.append("incluir_evidencia")

        if not selected_id.isdigit():
            action_err = "Selecione uma solicitacao valida."
        else:
            solicitacao = qs.filter(id=int(selected_id)).first()
            if not solicitacao:
                action_err = "Solicitacao nao encontrada ou nao esta reprovada."
            else:
                comentario_parts = []
                if motivo:
                    comentario_parts.append(motivo)
                if checklist:
                    comentario_parts.append("checklist: " + ", ".join(checklist))
                update_fields = {"atualizado_em"}
                if prazo_raw:
                    comentario_parts.append(f"prazo_desejado: {prazo_raw}")
                    prazo_data = _parse_date(prazo_raw)
                    if prazo_data:
                        solicitacao.prazo_estimado = prazo_data
                        update_fields.add("prazo_estimado")
                if anexos:
                    solicitacao.anexos = anexos
                    update_fields.add("anexos")
                comentario_final = " | ".join(comentario_parts)
                if update_fields:
                    solicitacao.save(update_fields=list(update_fields))
                solicitacao.mudar_status(
                    SolicitacaoStatus.RETRABALHO,
                    request.user,
                    comentario=comentario_final,
                )
                ok = True
                action_msg = "Retrabalho solicitado."
                qs = qs.exclude(id=solicitacao.id)

    solicitacoes = [_decorate_solicitacao(sol) for sol in qs[:200]]
    pendentes_count = qs.count()
    if not selected_id and request.GET.get("id", "").isdigit():
        selected_id = request.GET.get("id", "").strip()

    return render(
        request,
        "portal/solicitar_retrabalho.html",
        {
            "ok": ok,
            "action_msg": action_msg,
            "action_err": action_err,
            "motivo": motivo,
            "solicitacoes": solicitacoes,
            "selected_id": selected_id,
            "admin_mode": admin_mode,
            "pendentes_count": pendentes_count,
            "filters": {"q": q_filter},
        },
    )


@login_required
def retorno_final(request):
    admin_mode = _require_group_or_admin(request, "SOLICITANTE")
    q_filter = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip().lower()

    base_qs = Solicitacao.objects.select_related("criado_por", "atribuido_para").filter(
        status__in=[
            SolicitacaoStatus.APROVADO,
            SolicitacaoStatus.CANCELADO,
        ]
    )
    if not admin_mode:
        base_qs = base_qs.filter(criado_por=request.user)
    retorno_status_map = {
        "retorno_final": {SolicitacaoStatus.APROVADO},
        "cancelado": {SolicitacaoStatus.CANCELADO},
    }
    if status_filter in retorno_status_map:
        base_qs = base_qs.filter(status__in=retorno_status_map[status_filter])
    base_qs = _apply_q_filter(base_qs, q_filter)

    concluidas = [_decorate_solicitacao(sol) for sol in base_qs[:200]]
    for sol in concluidas:
        if sol.status == SolicitacaoStatus.APROVADO:
            sol.status_label = "Aprovado"
    concluidas_count = base_qs.count()

    return render(
        request,
        "portal/retorno_final.html",
        {
            "concluidas": concluidas,
            "admin_mode": admin_mode,
            "concluidas_count": concluidas_count,
            "filters": {"q": q_filter, "status": status_filter},
        },
    )


@login_required
def visualizar_solicitacao(request):
    admin_mode = _require_group_or_admin(request, "SOLICITANTE")
    solicitacao_id = request.GET.get("id", "").strip()
    if not solicitacao_id:
        solicitacao_id = request.POST.get("solicitacao_id", "").strip()
    back_target = request.GET.get("back", "").strip()
    q_filter = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    action_key = request.GET.get("acao", "").strip()
    if not action_key:
        action_key = request.POST.get("acao", "").strip()

    action_meta = {
        "retrabalho": {
            "label": "Retrabalho",
            "status": SolicitacaoStatus.RETRABALHO,
            "success": "Retrabalho solicitado.",
        },
        "aprovar": {
            "label": "Aprovar",
            "status": SolicitacaoStatus.APROVADO,
            "success": "Solicitacao aprovada.",
        },
        "cancelar": {
            "label": "Cancelar",
            "status": SolicitacaoStatus.CANCELADO,
            "success": "Solicitacao cancelada.",
        },
    }
    action_info = action_meta.get(action_key)
    action_label = action_info["label"] if action_info else ""
    action_msg = ""
    action_err = ""
    observacao_retrabalho = ""
    observacao_final = ""
    final_view = None

    if not solicitacao_id.isdigit():
        return redirect("aprovar_reaprovar")

    qs = Solicitacao.objects.select_related("criado_por", "atribuido_para")
    if not admin_mode:
        qs = qs.filter(criado_por=request.user)

    solicitacao = get_object_or_404(qs, id=int(solicitacao_id))
    if request.method == "GET":
        log_action(
            request,
            "solicitante_abrir_solicitacao",
            solicitacao=solicitacao,
            descricao="Solicitação aberta para visualização.",
            extra={"acao": action_key or "visualizar", "admin_mode": admin_mode},
        )
    if request.method == "POST" and action_info:
        observacao_retrabalho = request.POST.get("observacao_retrabalho", "").strip()
        observacao_final = request.POST.get("observacao_final", "").strip()
        comentario = (
            observacao_retrabalho
            if action_key == "retrabalho"
            else observacao_final
        )
        allowed_statuses = _SOLICITANTE_ACTION_ALLOWED_STATUSES.get(action_key)
        if allowed_statuses and solicitacao.status not in allowed_statuses:
            action_err = _SOLICITANTE_ACTION_STATUS_ERR
        else:
            solicitacao.mudar_status(
                action_info["status"],
                request.user,
                comentario=comentario,
            )
            action_log_map = {
                "aprovar": "solicitante_aprovar",
                "retrabalho": "solicitante_retrabalho",
                "cancelar": "solicitante_cancelar",
            }
            log_action(
                request,
                action_log_map.get(action_key, "solicitante_acao"),
                solicitacao=solicitacao,
                descricao=action_info["label"],
                extra={"comentario": comentario or ""},
            )
            action_msg = action_info["success"]
    elif request.method == "POST" and not action_info:
        action_err = "Acao invalida."

    solicitacao = _decorate_solicitacao(solicitacao)
    if back_target == "retorno_final" and solicitacao.status == SolicitacaoStatus.APROVADO:
        solicitacao.status_label = "Aprovado"
    if not action_info:
        final_label_map = {
            SolicitacaoStatus.APROVADO: "Aprovado",
            SolicitacaoStatus.REPROVADO: "Reprovado",
            SolicitacaoStatus.CANCELADO: "Cancelado",
            SolicitacaoStatus.RETRABALHO: "Retrabalho",
            SolicitacaoStatus.CONCLUIDO: "Concluido",
        }
        final_log = (
            SolicitacaoLog.objects.filter(
                solicitacao_id=solicitacao.id,
                status_para__in=[
                    SolicitacaoStatus.APROVADO,
                    SolicitacaoStatus.REPROVADO,
                    SolicitacaoStatus.CANCELADO,
                    SolicitacaoStatus.RETRABALHO,
                    SolicitacaoStatus.CONCLUIDO,
                ],
            )
            .order_by("-criado_em")
            .first()
        )
        status_for_final = final_log.status_para if final_log else solicitacao.status
        if status_for_final in final_label_map:
            if final_log:
                observacao = final_log.comentario or "-"
            else:
                comentario_map = {
                    SolicitacaoStatus.APROVADO: solicitacao.aprovado_comentario,
                    SolicitacaoStatus.REPROVADO: solicitacao.reprovado_comentario,
                    SolicitacaoStatus.CANCELADO: solicitacao.cancelado_comentario,
                    SolicitacaoStatus.RETRABALHO: solicitacao.retrabalho_comentario,
                    SolicitacaoStatus.CONCLUIDO: solicitacao.concluido_comentario,
                }
                observacao = comentario_map.get(status_for_final) or "-"
            final_view = {
                "disposicao_label": final_label_map.get(
                    status_for_final, status_for_final
                ),
                "observacao": observacao,
                "is_retrabalho": status_for_final == SolicitacaoStatus.RETRABALHO,
            }

    back_url = ""
    back_label = ""
    if back_target == "aprovar_reaprovar":
        back_url = reverse("aprovar_reaprovar")
        params = {}
        if q_filter:
            params["q"] = q_filter
        if params:
            back_url = f"{back_url}?{urlencode(params)}"
        back_label = "Voltar para aprovar/reprovar"
    elif back_target == "status_do_projeto":
        back_url = reverse("status_do_projeto")
        params = {}
        if status_filter:
            params["status"] = status_filter
        if q_filter:
            params["q"] = q_filter
        if params:
            back_url = f"{back_url}?{urlencode(params)}"
        back_label = "Voltar para status"
    elif back_target == "status_finalizadas":
        back_url = reverse("status_finalizadas")
        back_label = "Voltar para finalizadas"
    elif back_target == "retorno_final":
        back_url = reverse("retorno_final")
        params = {}
        if q_filter:
            params["q"] = q_filter
        if params:
            back_url = f"{back_url}?{urlencode(params)}"
        back_label = "Voltar para retorno final"

    if request.method == "POST":
        if action_key in {"aprovar", "cancelar"}:
            target_url = reverse("retorno_final")
        else:
            target_url = back_url or reverse("status_do_projeto")
        if action_msg:
            messages.success(request, action_msg)
        if action_err:
            messages.error(request, action_err)
        return redirect(target_url)

    return render(
        request,
        "portal/preencher_solicitacao.html",
        {
            "ok": False,
            "solicitacao": solicitacao,
            "status_interno": "PRONTO_PARA_ENVIO",
            "pendentes": [],
            "modo_retrabalho": False,
            "hero_title": "Controle de Projeto",
            "hero_subtitle": "Visualize o retorno do projetista antes de aprovar ou reprovar.",
            "back_url_name": "",
            "back_label": back_label,
            "back_url": back_url,
            "view_mode": True,
            "sidebar_template": "portal/_sidebar_solicitante.html",
            "action_mode": bool(action_info),
            "action_key": action_key,
            "action_label": action_label,
            "action_msg": action_msg,
            "action_err": action_err,
            "observacao_retrabalho": observacao_retrabalho,
            "observacao_final": observacao_final,
            "final_view": final_view,
        },
    )


# =========================
# PROJETISTA
# =========================
@login_required
@group_required("PROJETISTA")
@login_required
@group_required("PROJETISTA")
def projetista_dashboard(request):
    kpis = _get_projetista_kpis(request.user)
    admin_mode = _is_admin_user(request.user)
    extras = _get_projetista_dashboard_extras(request.user, include_all=admin_mode)

    return render(
        request,
        "portal/projetista_dashboard.html",
        {
            **kpis,
            "admin_mode": admin_mode,
            **extras,
        },
    )


@login_required
@group_required("PROJETISTA")
def fila_trabalho(request):
    solicitacoes_raw = list(
        Solicitacao.objects.select_related("criado_por")
        .filter(
            Q(status=SolicitacaoStatus.EM_FILA),
            Q(atribuido_para=request.user) | Q(atribuido_para__isnull=True),
        )
        .order_by(*_baseline_priority_order())[:200]
    )
    gv_proj_map = _build_gv_proj_map(solicitacoes_raw)
    solicitacoes = [
        _decorate_solicitacao(sol, gv_proj_map=gv_proj_map)
        for sol in solicitacoes_raw
    ]
    return render(request, "portal/fila_trabalho.html", {"solicitacoes": solicitacoes})


def _preencher_solicitacao_base(request, modo="preencher"):
    ok = False
    solicitacao = None
    final_view = None
    base_qs = Solicitacao.objects.filter(
        Q(atribuido_para=request.user) | Q(atribuido_para__isnull=True)
    )
    pendentes = list(
        base_qs.filter(
            status__in=[SolicitacaoStatus.EM_FILA, SolicitacaoStatus.EM_PROJETO],
        )
        .order_by(*_baseline_priority_order())[:200]
    )
    allowed_statuses = [
        SolicitacaoStatus.EM_FILA,
        SolicitacaoStatus.EM_PROJETO,
        SolicitacaoStatus.RETRABALHO,
    ]
    solicitacao_id = request.GET.get("id") or request.POST.get("solicitacao_id")
    if solicitacao_id and str(solicitacao_id).isdigit():
        solicitacao = (
            base_qs.filter(id=int(solicitacao_id), status__in=allowed_statuses).first()
        )

    if modo == "retrabalho" and not solicitacao:
        return redirect("retrabalho_solicitado")

    if request.method == "GET" and solicitacao:
        log_action(
            request,
            "projetista_abrir_solicitacao",
            solicitacao=solicitacao,
            descricao="Solicitação aberta para preenchimento.",
            extra={"modo": modo},
        )

    if request.method == "POST" and solicitacao:
        solicitacao.descricao_tecnica = request.POST.get("descricao_tecnica", "").strip()
        solicitacao.material = request.POST.get("material", "").strip()
        solicitacao.tratamento = request.POST.get("tratamento", "").strip()
        solicitacao.dim_criticas = request.POST.get("dim_criticas", "").strip()
        if request.FILES.get("anexos"):
            solicitacao.anexos = request.FILES.get("anexos")
        solicitacao.prazo_estimado = _parse_date(request.POST.get("prazo", ""))
        solicitacao.observacoes_aprovacao = request.POST.get("obs", "").strip()

        if solicitacao.atribuido_para_id is None:
            solicitacao.atribuido_para = request.user

        acao = request.POST.get("acao", "").strip()
        if acao in {"pronto", "enviar"}:
            solicitacao.status = SolicitacaoStatus.AGUARDANDO_APROVACAO
        else:
            solicitacao.status = SolicitacaoStatus.EM_PROJETO

        solicitacao.save()
        is_enviar = acao in {"pronto", "enviar"}
        if modo == "retrabalho":
            action_key = "projetista_corrigir_retrabalho"
        else:
            action_key = (
                "projetista_enviar_aprovacao"
                if is_enviar
                else "projetista_salvar_rascunho"
            )
        log_action(
            request,
            action_key,
            solicitacao=solicitacao,
            descricao="Atualização do projetista.",
            extra={"acao": acao, "status": solicitacao.status, "modo": modo},
        )
        ok = True

    status_interno = "RASCUNHO"
    if solicitacao and solicitacao.status in [
        SolicitacaoStatus.AGUARDANDO_APROVACAO,
        SolicitacaoStatus.APROVADO,
        SolicitacaoStatus.REPROVADO,
        SolicitacaoStatus.CONCLUIDO,
    ]:
        status_interno = "PRONTO_PARA_ENVIO"

    if modo == "retrabalho":
        hero_title = "Retrabalho solicitado"
        hero_subtitle = "Revise o item devolvido, ajuste os dados e devolva para aprovacao."
        back_url_name = "retrabalho_solicitado"
        back_label = "Voltar para retrabalhos"
    else:
        hero_title = "Preencher solicitacao"
        hero_subtitle = "Complete o que falta, anexe evidencias/desenhos e deixe pronto para aprovacao."
        back_url_name = "preencher_solicitacao"
        back_label = "Voltar para lista"

    if solicitacao:
        solicitacao = _decorate_solicitacao(solicitacao)
        final_log = (
            SolicitacaoLog.objects.filter(
                solicitacao_id=solicitacao.id,
                status_para__in=[
                    SolicitacaoStatus.APROVADO,
                    SolicitacaoStatus.REPROVADO,
                    SolicitacaoStatus.CANCELADO,
                    SolicitacaoStatus.RETRABALHO,
                ],
            )
            .order_by("-criado_em")
            .first()
        )
        if final_log:
            final_label_map = {
                SolicitacaoStatus.APROVADO: "Aprovado",
                SolicitacaoStatus.REPROVADO: "Reprovado",
                SolicitacaoStatus.CANCELADO: "Cancelado",
                SolicitacaoStatus.RETRABALHO: "Retrabalho",
            }
            final_view = {
                "disposicao_label": final_label_map.get(
                    final_log.status_para, final_log.status_para
                ),
                "observacao": final_log.comentario or "-",
                "is_retrabalho": final_log.status_para == SolicitacaoStatus.RETRABALHO,
            }

    if pendentes:
        gv_proj_map = _build_gv_proj_map(pendentes)
        pendentes = [_decorate_solicitacao(sol, gv_proj_map=gv_proj_map) for sol in pendentes]

    return render(
        request,
        "portal/preencher_solicitacao.html",
        {
            "ok": ok,
            "solicitacao": solicitacao,
            "status_interno": status_interno,
            "pendentes": pendentes,
            "modo_retrabalho": modo == "retrabalho",
            "hero_title": hero_title,
            "hero_subtitle": hero_subtitle,
            "back_url_name": back_url_name,
            "back_label": back_label,
            "view_mode": False,
            "sidebar_template": "portal/_sidebar_projetista.html",
            "final_view": final_view,
        },
    )


@login_required
@group_required("PROJETISTA")
def preencher_solicitacao(request):
    return _preencher_solicitacao_base(request, modo="preencher")


@login_required
@group_required("PROJETISTA")
def corrigir_retrabalho(request):
    return _preencher_solicitacao_base(request, modo="retrabalho")


@login_required
@group_required("PROJETISTA")
def retrabalho_solicitado(request):
    base_qs = Solicitacao.objects.filter(
        Q(atribuido_para=request.user) | Q(atribuido_para__isnull=True),
        status=SolicitacaoStatus.RETRABALHO,
    )
    solicitacoes_raw = list(
        base_qs.select_related("criado_por", "atribuido_para")
        .order_by(*_baseline_priority_order())[:200]
    )

    comentarios = {}
    if solicitacoes_raw:
        try:
            SolicitacaoLog = apps.get_model("portal", "SolicitacaoLog")
        except LookupError:
            SolicitacaoLog = None
        if SolicitacaoLog:
            ids = [s.id for s in solicitacoes_raw]
            logs = (
                SolicitacaoLog.objects.filter(
                    solicitacao_id__in=ids,
                    status_para=SolicitacaoStatus.RETRABALHO,
                )
                .order_by("solicitacao_id", "-criado_em")
            )
            for log in logs:
                if log.solicitacao_id not in comentarios:
                    comentarios[log.solicitacao_id] = log.comentario

    gv_proj_map = _build_gv_proj_map(solicitacoes_raw)
    solicitacoes = [
        _decorate_solicitacao(sol, gv_proj_map=gv_proj_map)
        for sol in solicitacoes_raw
    ]
    for item in solicitacoes:
        item.retrabalho_comentario = comentarios.get(item.id, "")

    return render(
        request,
        "portal/retrabalho_solicitado.html",
        {"solicitacoes": solicitacoes},
    )


@login_required
@group_required("PROJETISTA")
def enviar_aprovacao(request):
    ok = False
    if request.method == "POST":
        ok = True
    return render(request, "portal/enviar_aprovacao.html", {"ok": ok})


# =========================
# DISPOSITIVOS
# =========================
@login_required
@group_required("DISPOSITIVOS")
def dispositivos_dashboard(request):
    context = _get_dispositivos_dashboard_context()
    return render(request, "portal/dispositivos_dashboard.html", context)


def _ok_post(request):
    return request.method == "POST"


def _log_dispositivos_form(request, action_key: str, descricao: str) -> None:
    if request.method != "POST":
        return
    log_action(
        request,
        action_key,
        descricao=descricao,
        extra={"view": action_key},
        entidade="Dispositivos",
    )


@login_required
@group_required("DISPOSITIVOS")
def disp_novo_completo(request):
    _log_dispositivos_form(
        request,
        "dispositivos_disp_novo_completo",
        "Envio de formulário: novo completo.",
    )
    return render(request, "portal/disp_novo_completo.html", {"ok": _ok_post(request)})


@login_required
@group_required("DISPOSITIVOS")
def disp_novo_parte_retrabalhada(request):
    _log_dispositivos_form(
        request,
        "dispositivos_disp_novo_parte_retrabalhada",
        "Envio de formulário: novo parte retrabalhada.",
    )
    return render(request, "portal/disp_novo_parte_retrabalhada.html", {"ok": _ok_post(request)})


@login_required
@group_required("DISPOSITIVOS")
def disp_novo_parte_existente(request):
    _log_dispositivos_form(
        request,
        "dispositivos_disp_novo_parte_existente",
        "Envio de formulário: novo parte existente.",
    )
    return render(request, "portal/disp_novo_parte_existente.html", {"ok": _ok_post(request)})


@login_required
@group_required("DISPOSITIVOS")
def disp_usar_projeto_existente(request):
    _log_dispositivos_form(
        request,
        "dispositivos_disp_usar_projeto_existente",
        "Envio de formulário: usar projeto existente.",
    )
    return render(request, "portal/disp_usar_projeto_existente.html", {"ok": _ok_post(request)})


@login_required
@group_required("DISPOSITIVOS")
def disp_regularizar_art(request):
    _log_dispositivos_form(
        request,
        "dispositivos_disp_regularizar_art",
        "Envio de formulário: regularizar ART.",
    )
    return render(request, "portal/disp_regularizar_art.html", {"ok": _ok_post(request)})


@login_required
@group_required("DISPOSITIVOS")
def disp_retrabalhar_disp_existente(request):
    _log_dispositivos_form(
        request,
        "dispositivos_disp_retrabalhar_disp_existente",
        "Envio de formulário: retrabalhar disp existente.",
    )
    return render(request, "portal/disp_retrabalhar_disp_existente.html", {"ok": _ok_post(request)})


@login_required
@group_required("DISPOSITIVOS")
def disp_usar_disp_existente_regularizado(request):
    _log_dispositivos_form(
        request,
        "dispositivos_disp_usar_disp_existente_regularizado",
        "Envio de formulário: usar disp existente regularizado.",
    )
    return render(request, "portal/disp_usar_disp_existente_regularizado.html", {"ok": _ok_post(request)})


@login_required
@group_required("DISPOSITIVOS")
def disp_cancelar_frnr(request):
    _log_dispositivos_form(
        request,
        "dispositivos_disp_cancelar_frnr",
        "Envio de formulário: cancelar FRNR.",
    )
    return render(request, "portal/disp_cancelar_frnr.html", {"ok": _ok_post(request)})


@login_required
@group_required("DISPOSITIVOS")
def disp_job_irma(request):
    _log_dispositivos_form(
        request,
        "dispositivos_disp_job_irma",
        "Envio de formulário: job irmã.",
    )
    return render(request, "portal/disp_job_irma.html", {"ok": _ok_post(request)})


@login_required
@group_required("DISPOSITIVOS")
def disp_fabricacao_interna(request):
    _log_dispositivos_form(
        request,
        "dispositivos_disp_fabricacao_interna",
        "Envio de formulário: fabricação interna.",
    )
    return render(request, "portal/disp_fabricacao_interna.html", {"ok": _ok_post(request)})


@login_required
@group_required("DISPOSITIVOS")
def disp_retrabalhar_projeto(request):
    _log_dispositivos_form(
        request,
        "dispositivos_disp_retrabalhar_projeto",
        "Envio de formulário: retrabalhar projeto.",
    )
    return render(request, "portal/disp_retrabalhar_projeto.html", {"ok": _ok_post(request)})
