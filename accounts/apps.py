"""
Configuração da app de accounts (contas/usuários).
"""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """
    Configuração da aplicação de contas.
    
    Esta app é responsável por:
    - Autenticação de usuários
    - Perfis de usuário
    - Gerenciamento de grupos e permissões
    """
    name = 'accounts'

    def ready(self):
        """
        Chamado quando a app está pronta.
        
        Importa os signals para que os listeners sejam registrados
        e possam responder a eventos do Django.
        """
        from . import signals  # noqa: F401 (importado mas não usado diretamente)

