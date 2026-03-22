# config/urls.py
"""
Configuração central de URLs do projeto Django.

Define todas as rotas da aplicação, incluindo:
- Admin do Django
- Autenticação (login/logout)
- Portais e dashboards por tipo de usuário
- Telas específicas para cada funcionalidade
"""

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

from accounts import views as accounts_views
from portal import views as portal_views


urlpatterns = [
    # ====================
    # ADMIN DO DJANGO
    # ====================
    path("admin/", admin.site.urls),

    # Accounts (login)
    path("accounts/", include("accounts.urls")),

    # Logout
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),

    # Portal home (mant�m o seu)
    path("portal/", accounts_views.portal_home, name="portal_home"),

    # Alias (se em algum lugar estiver usando portal_redirect)
    path("portal/", accounts_views.portal_home, name="portal_redirect"),

    # Dashboards
    path("portal/admin/", accounts_views.dashboard_admin, name="dashboard_admin"),
    path("portal/solicitante/", accounts_views.dashboard_solicitante, name="dashboard_solicitante"),
    path("portal/projetista/", accounts_views.dashboard_projetista, name="dashboard_projetista"),
    path("portal/dispositivos/", accounts_views.dashboard_dispositivos, name="dashboard_dispositivos"),

    # Configuracoes do usuario
    path("portal/configuracoes/", portal_views.configuracoes, name="configuracoes"),

    # Notificacoes (rascunho)
    path("portal/notificacoes/", portal_views.notificacoes, name="notificacoes"),

    # Alias (antigos)
    path("portal/admin/", accounts_views.dashboard_admin, name="admin_dashboard"),
    path("portal/solicitante/", accounts_views.dashboard_solicitante, name="solicitante_dashboard"),
    path("portal/projetista/", accounts_views.dashboard_projetista, name="projetista_dashboard"),

    # ============================
    # ADMIN � Subtelas (rascunho)
    # ============================
    path(
        "portal/admin/banco-de-dados/",
        portal_views.admin_banco_de_dados,
        name="admin_banco_de_dados",
    ),
    path(
        "portal/admin/dashboard-status-series/",
        portal_views.admin_dashboard_status_series,
        name="admin_dashboard_status_series",
    ),
    path(
        "portal/admin/solicitantes/",
        portal_views.admin_solicitantes,
        name="admin_solicitantes",
    ),
    path(
        "portal/admin/projetistas/",
        portal_views.admin_projetistas,
        name="admin_projetistas",
    ),
    path(
        "portal/admin/dispositivos/",
        portal_views.admin_dispositivos,
        name="admin_dispositivos",
    ),
    path(
        "portal/admin/configuracoes/",
        TemplateView.as_view(template_name="portal/admin_configuracoes.html"),
        name="admin_configuracoes",
    ),
    path(
        "portal/admin/usuarios-permissoes/",
        portal_views.admin_usuarios_permissoes,
        name="admin_usuarios_permissoes",
    ),
    path(
        "portal/admin/auditoria-logs/",
        portal_views.admin_auditoria_logs,
        name="admin_auditoria_logs",
    ),

    # Subtelas gen�ricas
    path("portal/novo-apontamento/", portal_views.novo_apontamento, name="novo_apontamento"),
    path("portal/tabela-consulta/", portal_views.tabela_consulta, name="tabela_consulta"),
    path("portal/registro/", portal_views.registro_placeholder, name="registro_placeholder"),
    path("portal/pagina/", portal_views.pagina_placeholder, name="pagina_placeholder"),

    # SOLICITANTE � telas
    path("portal/status-do-projeto/", portal_views.status_do_projeto, name="status_do_projeto"),
    path("portal/status-finalizadas/", portal_views.status_finalizadas, name="status_finalizadas"),
    path("portal/busca-solicitacao/", portal_views.buscar_solicitacao, name="buscar_solicitacao"),
    path("portal/dispositivos/descricao/", portal_views.buscar_descricao_dispositivo, name="buscar_descricao_dispositivo"),
    path("portal/aprovar-reaprovar/", portal_views.aprovar_reaprovar, name="aprovar_reaprovar"),
    path("portal/solicitar-retrabalho/", portal_views.solicitar_retrabalho, name="solicitar_retrabalho"),
    path("portal/retorno-final/", portal_views.retorno_final, name="retorno_final"),
    path("portal/visualizar-solicitacao/", portal_views.visualizar_solicitacao, name="visualizar_solicitacao"),

    # PROJETISTA � telas
    path("portal/fila-trabalho/", portal_views.fila_trabalho, name="fila_trabalho"),
    path("portal/preencher-solicitacao/", portal_views.preencher_solicitacao, name="preencher_solicitacao"),
    path("portal/retrabalho-solicitado/", portal_views.retrabalho_solicitado, name="retrabalho_solicitado"),
    path("portal/retrabalho-corrigir/", portal_views.corrigir_retrabalho, name="corrigir_retrabalho"),
    path("portal/enviar-aprovacao/", portal_views.enviar_aprovacao, name="enviar_aprovacao"),

    # DISPOSITIVOS � telas
    path("portal/dispositivos/dashboard/", portal_views.dispositivos_dashboard, name="dispositivos_dashboard"),
    path("portal/dispositivos/novo-completo/", portal_views.disp_novo_completo, name="disp_novo_completo"),
    path("portal/dispositivos/novo-parte-retrabalhada/", portal_views.disp_novo_parte_retrabalhada, name="disp_novo_parte_retrabalhada"),
    path("portal/dispositivos/novo-parte-existente/", portal_views.disp_novo_parte_existente, name="disp_novo_parte_existente"),
    path("portal/dispositivos/usar-projeto-existente/", portal_views.disp_usar_projeto_existente, name="disp_usar_projeto_existente"),
    path("portal/dispositivos/regularizar-art/", portal_views.disp_regularizar_art, name="disp_regularizar_art"),
    path("portal/dispositivos/retrabalhar-disp-existente/", portal_views.disp_retrabalhar_disp_existente, name="disp_retrabalhar_disp_existente"),
    path("portal/dispositivos/usar-disp-existente-regularizado/", portal_views.disp_usar_disp_existente_regularizado, name="disp_usar_disp_existente_regularizado"),
    path("portal/dispositivos/cancelar-frnr/", portal_views.disp_cancelar_frnr, name="disp_cancelar_frnr"),
    path("portal/dispositivos/job-irma/", portal_views.disp_job_irma, name="disp_job_irma"),
    path("portal/dispositivos/fabricacao-interna/", portal_views.disp_fabricacao_interna, name="disp_fabricacao_interna"),
    path("portal/dispositivos/retrabalhar-projeto/", portal_views.disp_retrabalhar_projeto, name="disp_retrabalhar_projeto"),
]

if settings.DEBUG:
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

