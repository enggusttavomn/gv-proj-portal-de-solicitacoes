"""
Modelos da aplicação de contas (accounts).

Este módulo define modelos relacionados a perfis de usuários no sistema.
"""

from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """
    Modelo para armazenar informações adicionais do usuário.
    
    Relaciona-se com o modelo de usuário do Django através de um relacionamento
    OneToOne, permitindo adicionar dados extras como foto de perfil.
    
    Atributos:
        user: Relacionamento One-to-One com o usuário Django
        photo: Foto do perfil do usuário (opcional)
    """
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    # Campo para armazenar a foto do perfil do usuário
    photo = models.ImageField(upload_to="user_photos/", blank=True, null=True)

    def __str__(self):
        """Retorna uma representação legível do perfil."""
        return f"Profile: {self.user.get_username()}"
