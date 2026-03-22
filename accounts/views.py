# accounts/views.py
"""
Visualizações da aplicação de contas (accounts).

Responsável pelo:
- Login de usuários
- Redirecionamento para dashboards apropriados
- Controle de acesso baseado em grupos
"""

from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.template import loader

from .forms import DropdownLoginForm
from portal.views import (
    _get_admin_dashboard_context,
    _get_dispositivos_dashboard_context,
    _get_projetista_kpis,
    _get_solicitante_dashboard_extras,
    _get_solicitante_status_counts,
)


def _has_group(user, group_name: str) -> bool:
    """
    Verifica se um usuário pertence a um grupo específico.
    
    Args:
        user: Objeto User do Django
        group_name: Nome do grupo (ex: "ADMIN", "PROJETISTA", "SOLICITANTE")
        
    Returns:
        bool: True se o usuário está autenticado E pertence ao grupo, False caso contrário
    """
    return user.is_authenticated and user.groups.filter(name=group_name).exists()


def login_view(request):
    """
    View responsável pelo login dos usuários.
    
    GET: Exibe o formulário de login com dropdown de usuários
    POST: Processa a autenticação e redireciona para o dashboard apropriado
    
    Args:
        request: HttpRequest objeto
        
    Returns:
        HttpResponse: Renderiza o template de login ou redireciona após autenticação bem-sucedida
        
    Fluxo:
        1. Se POST e formulário válido, tenta autenticar o usuário
        2. Se bem-sucedido, faz login e redireciona para /portal/ (portal_home)
        3. portal_home então redireciona para o dashboard específico do usuário
    """
    error = None

    if request.method == "POST":
        form = DropdownLoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data.get("username", "")
            password = form.cleaned_data.get("password", "")

            if not username or not password:
                error = "Selecione o usuário e digite a senha."
            else:
                # Autentica o usuário com as credenciais fornecidas
                user = authenticate(request, username=username, password=password)
                if user is not None:
                    # Faz login do usuário na sessão
                    login(request, user)

                    # Vai para /portal/ (portal_home) e de lá redireciona para o dashboard correto
                    try:
                        return redirect(reverse("portal_home"))
                    except Exception:
                        return redirect("/portal/")
                else:
                    error = "Usuário ou senha inválidos."
        else:
            error = "Selecione o usuário e digite a senha."
    else:
        # GET request - exibe o formulário vazio
        form = DropdownLoginForm()

    # ===== DETECTOR DO TEMPLATE REAL (mantive para debug) =====
    tpl = loader.get_template("accounts/login.html")
    print(">>> TEMPLATE REAL DO LOGIN:", tpl.origin.name)
    # ==========================================================

    return render(request, "accounts/login.html", {"form": form, "error": error})


# ====================================================================
# PORTAL / REDIRECIONAMENTO - View Central que Define o Fluxo de Acesso
# ====================================================================
@login_required(login_url="/accounts/login/")
def portal_home(request):
    """
    View responsável por redirecionar usuários para seu dashboard apropriado.
    
    /portal/ -> redireciona para o dashboard correto baseado no grupo do usuário
    
    Prioridade de acesso (ordem de verificação):
        1. ADMIN (superuser ou grupo ADMIN)
        2. DISPOSITIVOS
        3. PROJETISTA
        4. SOLICITANTE
    
    Args:
        request: HttpRequest objeto (deve estar autenticado - @login_required)
        
    Returns:
        HttpResponseRedirect: Redireciona para o dashboard apropriado ou página de erro
    """
    user = request.user

    # Prioridade: ADMIN > DISPOSITIVOS > PROJETISTA > SOLICITANTE
    if user.is_superuser or _has_group(user, "ADMIN"):
        return redirect("dashboard_admin")

    if _has_group(user, "DISPOSITIVOS"):
        return redirect("dashboard_dispositivos")

    if _has_group(user, "PROJETISTA"):
        return redirect("dashboard_projetista")

    if _has_group(user, "SOLICITANTE"):
        return redirect("dashboard_solicitante")

    # Se o usuário não tem nenhum grupo, exibe mensagem de erro
    return render(
        request,
        "portal/pagina_placeholder.html",
        {"mensagem": "Usuário sem grupo. Peça para um ADMIN atribuir um grupo."},
    )


# ====================================================================
# DASHBOARDS - Views Específicas para Cada Tipo de Usuário
# ====================================================================

@login_required(login_url="/accounts/login/")
def dashboard_admin(request):
    """
    Dashboard para administradores.
    
    Exibe informações de controle geral do sistema, como gestão de usuários,
    auditoria e estatísticas de todas as solicitações.
    
    Args:
        request: HttpRequest objeto
        
    Returns:
        HttpResponse: Renderiza template admin_dashboard.html
        
    Permissões:
        - Requer ser superuser OU estar no grupo ADMIN
    """
    user = request.user
    if not (user.is_superuser or _has_group(user, "ADMIN")):
        return redirect("portal_home")
    
    # Busca os dados para exibir no dashboard
    context = _get_admin_dashboard_context()
    return render(request, "portal/admin_dashboard.html", context)


@login_required(login_url="/accounts/login/")
def dashboard_solicitante(request):
    """
    Dashboard para solicitantes.
    
    Exibe as solicitações criadas pelo usuário (ou todas se for admin),
    com status de cada uma (em fila, em projeto, aguardando aprovação, etc).
    
    Args:
        request: HttpRequest objeto
        
    Returns:
        HttpResponse: Renderiza template solicitante_dashboard.html
        
    Permissões:
        - Requer estar no grupo SOLICITANTE OU ser admin
        - Admins veem todas as solicitações
        - Solicitantes veem apenas as suas próprias
    """
    user = request.user
    # Admin pode ver também
    if not (_has_group(user, "SOLICITANTE") or user.is_superuser or _has_group(user, "ADMIN")):
        return redirect("portal_home")
    
    # Flag para determinar se está em modo admin (pode ver tudo)
    admin_mode = user.is_superuser or _has_group(user, "ADMIN")
    
    # Busca contadores de status das solicitações
    counts = _get_solicitante_status_counts(user, include_all=admin_mode)
    extras = _get_solicitante_dashboard_extras(user, include_all=admin_mode)
    
    return render(
        request, 
        "portal/solicitante_dashboard.html", 
        {"admin_mode": admin_mode, **counts, **extras}
    )


@login_required(login_url="/accounts/login/")
def dashboard_projetista(request):
    """
    Dashboard para projetistas.
    
    Exibe as solicitações atribuídas ao projetista com suas respectivas
    informações técnicas, prazos e status de projeto.
    
    Args:
        request: HttpRequest objeto
        
    Returns:
        HttpResponse: Renderiza template projetista_dashboard.html
        
    Permissões:
        - Requer estar no grupo PROJETISTA OU ser admin
    """
    user = request.user
    # Admin pode ver também
    if not (_has_group(user, "PROJETISTA") or user.is_superuser or _has_group(user, "ADMIN")):
        return redirect("portal_home")
    
    # Busca KPIs (indicadores-chave de performance) do projetista
    kpis = _get_projetista_kpis(user)
    
    return render(request, "portal/projetista_dashboard.html", kpis)


@login_required(login_url="/accounts/login/")
def dashboard_dispositivos(request):
    """
    Dashboard para gerenciadores de dispositivos.
    
    Exibe informações sobre o catálogo de dispositivos, disponibilidade,
    e gerenciamento de componentes.
    
    Args:
        request: HttpRequest objeto
        
    Returns:
        HttpResponse: Renderiza template dispositivos_dashboard.html
        
    Permissões:
        - Requer estar no grupo DISPOSITIVOS OU ser admin
    """
    user = request.user
    # Admin pode ver também
    if not (_has_group(user, "DISPOSITIVOS") or user.is_superuser or _has_group(user, "ADMIN")):
        return redirect("portal_home")
    
    # Busca os dados do contexto de dispositivos
    context = _get_dispositivos_dashboard_context()
    
    return render(request, "portal/dispositivos_dashboard.html", context)


# ====================================================================
# COMPATIBILIDADE - Redirecionamento para Função Anterior
# ====================================================================

@login_required(login_url="/accounts/login/")
def dashboard(request):
    """
    View legada para compatibilidade com referências antigas.
    
    Mantém compatibilidade se algum lugar do código ainda chama "dashboard".
    Redireciona para portal_home que realiza a lógica correta de redirecionamento.
    
    Args:
        request: HttpRequest objeto
        
    Returns:
        HttpResponseRedirect: Redireciona para portal_home
    """
    return portal_home(request)
