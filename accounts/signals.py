"""
Signals (Sinais) da app de accounts.

Sinais são triggers que executam automaticamente em resposta a eventos
do Django, como criação ou modificação de objetos.
"""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Cria automaticamente um perfil para cada novo usuário.
    
    Este signal é disparado sempre que um User é salvo (criado ou modificado).
    Se for um novo usuário (created=True), cria um UserProfile vazio.
    
    Args:
        sender: Modelo que gerou o sinal (User)
        instance: Instância do User que foi salvo
        created: Boolean indicando se foi criado (True) ou modificado (False)
        **kwargs: Argumentos adicionais do signal
        
    Comportamento:
        - Se User foi criado: cria um UserProfile vazio
        - Se User não tem profile: cria um novo
    """
    if created:
        # Novo usuário - cria seu perfil automaticamente
        UserProfile.objects.create(user=instance)
        return

    # Se o usuário foi modificado e não tem perfil, cria um
    if not hasattr(instance, "profile"):
        UserProfile.objects.create(user=instance)
