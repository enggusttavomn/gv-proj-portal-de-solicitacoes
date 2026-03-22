# seed_users.py
"""
Script de seed (população) de usuários e grupos no banco de dados.

Este script cria automaticamente:
- Grupos de usuários (ADMIN, SOLICITANTE, PROJETISTA, DISPOSITIVOS)
- Usuários com as credenciais fornecidas no catálogo de usuários do projeto

Uso:
    python seed_users.py

Nota: Senha padrão é '123'. Em produção, use um gerenciador de senhas seguro.
"""

import os
import django

# Configurar o Django antes de usar modelos
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from accounts.directory import (
    DEFAULT_PASSWORD_PLACEHOLDER,
    PROFILE_KEY_INFO,
    USER_DIRECTORY_MAP,
)

User = get_user_model()


# =========================
# CRIAR/OBTER GRUPOS
# =========================
ADMIN, _ = Group.objects.get_or_create(name="ADMIN")
SOLICITANTE, _ = Group.objects.get_or_create(name="SOLICITANTE")
PROJETISTA, _ = Group.objects.get_or_create(name="PROJETISTA")
DISPOSITIVOS, _ = Group.objects.get_or_create(name="DISPOSITIVOS")

GROUP_NAME_MAP = {
    "ADMIN": ADMIN,
    "SOLICITANTE": SOLICITANTE,
    "PROJETISTA": PROJETISTA,
    "DISPOSITIVOS": DISPOSITIVOS,
}


# =========================
# CRIAR/ATUALIZAR USUÁRIOS
# =========================
created = []

for entry in USER_DIRECTORY_MAP.values():
    full_name = entry["full_name"].strip()
    parts = full_name.split(" ", 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else ""
    username = entry["sso"]
    email = entry.get("email", "")
    profile_key = entry["profile_key"]
    group_name = PROFILE_KEY_INFO.get(profile_key, {}).get("group") or "SOLICITANTE"

    user = User.objects.filter(username=username).first()
    if user:
        user.set_password(DEFAULT_PASSWORD_PLACEHOLDER)
        user.email = email or user.email
        user.first_name = first
        user.last_name = last
    else:
        user = User.objects.create_user(
            username=username,
            password=DEFAULT_PASSWORD_PLACEHOLDER,
            first_name=first,
            last_name=last,
            email=email,
        )

    user.groups.clear()
    if group_name in GROUP_NAME_MAP:
        user.groups.add(GROUP_NAME_MAP[group_name])
    user.is_staff = group_name == "ADMIN"
    user.is_active = True
    user.save()

    created.append((full_name, username, DEFAULT_PASSWORD_PLACEHOLDER, group_name))


# =========================
# EXIBIR RESULTADO
# =========================
print("\n=== USUÁRIOS CRIADOS/ATUALIZADOS ===")
for full_name, username, pwd, group_name in created:
    print(f"{full_name:20} | username={username} | senha={pwd} | grupo={group_name}")
print("\nOK.\n")
