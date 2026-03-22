# accounts/urls.py
"""
URL patterns da aplicação de contas (accounts).

Define as rotas para:
- Login de usuários
- Acesso ao dashboard
"""

from django.urls import path
from .views import login_view, dashboard

urlpatterns = [
    # Rota de login
    path("login/", login_view, name="login"),
    
    # Rota legada do dashboard (redireciona para portal_home)
    path("dashboard/", dashboard, name="dashboard"),
]
