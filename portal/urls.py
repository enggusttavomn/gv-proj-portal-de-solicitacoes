"""
URL patterns da app de portal.

Define as rotas internas da aplicação de portal.
Nota: As rotas principais estão em config/urls.py
"""

from django.urls import path
from . import views

urlpatterns = [
    # Redirecionamento padrão do portal (legado)
    path("", views.portal_redirect, name="portal_redirect"),

    # ============ ADMIN ============
    path("admin/", views.admin_dashboard, name="admin_dashboard"),
    path(
        "admin/dashboard-status-series/",
        views.admin_dashboard_status_series,
        name="admin_dashboard_status_series",
    ),
    path("admin/solicitantes/", views.admin_solicitantes, name="admin_solicitantes"),
    path("admin/projetistas/", views.admin_projetistas, name="admin_projetistas"),
    path("admin/banco-de-dados/", views.admin_banco_de_dados, name="admin_banco_de_dados"),

    # ============ USUÁRIOS (DASHBOARDS) ============
    path("solicitante/", views.solicitante_dashboard, name="solicitante_dashboard"),
    path("projetista/", views.projetista_dashboard, name="projetista_dashboard"),

    # ============ OUTROS (PLACEHOLDERS) ============
    path("novo-apontamento/", views.novo_apontamento, name="novo_apontamento"),
    path("tabela-consulta/", views.tabela_consulta, name="tabela_consulta"),
    path("registro/", views.registro_placeholder, name="registro_placeholder"),
    path("pagina/", views.pagina_placeholder, name="pagina_placeholder"),
]
