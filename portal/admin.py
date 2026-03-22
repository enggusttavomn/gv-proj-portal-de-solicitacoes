"""
Configuração do Django Admin para a app de portal.

Define como os modelos de solicitação, logs e dispositivos são exibidos
e gerenciados no painel administrativo do Django.
"""

from django.contrib import admin
from .models import Solicitacao, SolicitacaoLog, DispositivoCatalogo, AuditLog


@admin.register(Solicitacao)
class SolicitacaoAdmin(admin.ModelAdmin):
    """
    Admin para gerenciar solicitações.
    
    Exibe uma listagem com filtros e busca para facilitar a visualização
    e gerenciamento de solicitações do sistema.
    """
    # Colunas exibidas na listagem
    list_display = ("id", "titulo", "status", "prioridade", "criado_por", "atribuido_para", "criado_em")
    
    # Filtros disponíveis na lateral
    list_filter = ("status", "prioridade", "criado_em")
    
    # Campos pesquisáveis
    search_fields = ("id", "titulo", "descricao", "criado_por__username", "atribuido_para__username")
    
    # Campos que não podem ser editados (apenas leitura)
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(SolicitacaoLog)
class SolicitacaoLogAdmin(admin.ModelAdmin):
    """
    Admin para visualizar o histórico de mudanças de status.
    
    Permite rastreabilidade de todas as alterações de status
    que ocorreram nas solicitações.
    """
    # Colunas exibidas na listagem
    list_display = ("id", "solicitacao", "status_de", "status_para", "alterado_por", "criado_em")
    
    # Filtros disponíveis na lateral
    list_filter = ("status_de", "status_para", "criado_em")
    
    # Campos pesquisáveis
    search_fields = ("solicitacao__id", "alterado_por__username", "comentario")
    
    # Campos que não podem ser editados (apenas leitura)
    readonly_fields = ("criado_em",)


@admin.register(DispositivoCatalogo)
class DispositivoCatalogoAdmin(admin.ModelAdmin):
    """
    Admin para gerenciar o catálogo de dispositivos.
    
    Permite visualizar, criar, editar e deletar dispositivos
    do catálogo disponível no sistema.
    """
    # Colunas exibidas na listagem
    list_display = ("codigo", "descricao")
    
    # Campos pesquisáveis
    search_fields = ("codigo", "descricao")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Admin para visualizar auditoria geral do sistema.
    """
    list_display = ("id", "acao", "usuario", "grupo", "solicitacao", "criado_em")
    list_filter = ("acao", "grupo", "criado_em")
    search_fields = ("acao", "descricao", "usuario__username", "solicitacao__id")
    readonly_fields = ("criado_em",)
