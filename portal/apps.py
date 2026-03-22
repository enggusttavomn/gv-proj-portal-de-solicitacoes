"""
Configuração da app de portal.

Define o nome e comportamento da app no projeto Django.
"""

from django.apps import AppConfig


class PortalConfig(AppConfig):
    """
    Configuração da aplicação 'portal'.
    
    Portal é a app principal que contém toda a lógica de negócio
    do sistema de gerenciamento de solicitações e dispositivos.
    
    Atributos:
        name: Nome da aplicação
    """
    name = 'portal'

