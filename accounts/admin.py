"""
Configuração do Django Admin para a app de accounts (contas).

Define como os modelos de usuário e perfil são exibidos e editados
no painel administrativo do Django.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import UserProfile

User = get_user_model()


class UserProfileInline(admin.StackedInline):
    """
    Inline para editar o perfil do usuário junto com o usuário.
    
    Permite que ao editar um usuário no admin, você também possa
    editar sua foto de perfil na mesma página.
    """
    model = UserProfile
    can_delete = False  # Não permite deletar o perfil
    fields = ("photo",)  # Campos exibidos no inline
    fk_name = "user"  # Nome da chave estrangeira


class UserAdmin(BaseUserAdmin):
    """
    Customização do admin padrão de usuários do Django.
    
    Estende o BaseUserAdmin para adicionar o inline de perfil,
    permitindo edição de foto junto com dados do usuário.
    """
    inlines = (UserProfileInline,)  # Adiciona o inline de perfil


# Remove o registro padrão do User e registra com a customização
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
