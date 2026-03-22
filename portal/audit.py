"""
Helpers de auditoria para registro de ações no portal.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from django.utils import timezone

from .models import AuditLog, Solicitacao


AUDIT_ACTION_LABELS = {
    "solicitante_abrir_solicitacao": "Solicitante abriu solicitação",
    "solicitante_criar_solicitacao": "Solicitante criou solicitação",
    "solicitante_editar_solicitacao": "Solicitante editou solicitação",
    "solicitante_excluir_solicitacao": "Solicitante excluiu solicitação",
    "solicitante_aprovar": "Solicitante aprovou",
    "solicitante_retrabalho": "Solicitante pediu retrabalho",
    "solicitante_cancelar": "Solicitante cancelou",
    "projetista_abrir_solicitacao": "Projetista abriu solicitação",
    "projetista_salvar_rascunho": "Projetista salvou rascunho",
    "projetista_enviar_aprovacao": "Projetista enviou para aprovação",
    "projetista_corrigir_retrabalho": "Projetista corrigiu retrabalho",
    "dispositivos_disp_novo_completo": "Dispositivos: novo completo",
    "dispositivos_disp_novo_parte_retrabalhada": "Dispositivos: novo parte retrabalhada",
    "dispositivos_disp_novo_parte_existente": "Dispositivos: novo parte existente",
    "dispositivos_disp_usar_projeto_existente": "Dispositivos: usar projeto existente",
    "dispositivos_disp_regularizar_art": "Dispositivos: regularizar ART",
    "dispositivos_disp_retrabalhar_disp_existente": "Dispositivos: retrabalhar disp existente",
    "dispositivos_disp_usar_disp_existente_regularizado": "Dispositivos: usar disp existente regularizado",
    "dispositivos_disp_cancelar_frnr": "Dispositivos: cancelar FRNR",
    "dispositivos_disp_job_irma": "Dispositivos: job irmã",
    "dispositivos_disp_fabricacao_interna": "Dispositivos: fabricação interna",
    "dispositivos_disp_retrabalhar_projeto": "Dispositivos: retrabalhar projeto",
}


def _get_primary_group(user) -> str:
    if not user or not user.is_authenticated:
        return ""
    group = user.groups.values_list("name", flat=True).first()
    return group or ""


def _get_client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def log_action(
    request,
    action: str,
    solicitacao: Optional[Solicitacao] = None,
    descricao: str = "",
    extra: Optional[Dict[str, Any]] = None,
    entidade: str = "",
    entidade_id: Optional[int] = None,
) -> None:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return
    try:
        AuditLog.objects.create(
            acao=action,
            descricao=descricao or "",
            usuario=user,
            grupo=_get_primary_group(user),
            solicitacao=solicitacao,
            entidade=entidade or (solicitacao.__class__.__name__ if solicitacao else ""),
            entidade_id=entidade_id or (solicitacao.id if solicitacao else None),
            dados=extra or None,
            ip=_get_client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT", "") or "")[:256],
            path=(request.path or "")[:200],
            method=(request.method or "")[:10],
            criado_em=timezone.now(),
        )
    except Exception:
        # Falha de auditoria não pode impedir a ação principal.
        return
