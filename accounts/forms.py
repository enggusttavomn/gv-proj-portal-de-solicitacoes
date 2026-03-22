# accounts/forms.py
"""
Formularios da aplicacao de contas (accounts).

Define formulários customizados para login e gerenciamento de usuarios.
"""

from django import forms
from django.contrib.auth import get_user_model

from accounts.directory import find_directory_entry

User = get_user_model()


class DropdownLoginForm(forms.Form):
    """
    Formulario de login com dropdown de usuarios.

    O dropdown lista todos os usuarios ativos (nao superusuarios) e
    exige senha para concluir o login.
    """

    username = forms.ChoiceField(
        label="Usuario",
        choices=[],
        widget=forms.Select(attrs={"class": "input", "id": "user"})
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={
            "class": "input",
            "id": "password",
            "placeholder": "Digite a senha",
            "autocomplete": "current-password",
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        qs = User.objects.filter(
            is_active=True,
            is_superuser=False
        ).order_by("first_name", "last_name", "username")

        choices = [("", "Selecione...")]
        for u in qs:
            full_name = (u.get_full_name() or "").strip()
            full_name_guess = ""
            if not full_name:
                username_guess = (u.username or "").strip()
                if username_guess and "@" not in username_guess:
                    normalized = (
                        username_guess
                        .replace(".", " ")
                        .replace("_", " ")
                        .replace("-", " ")
                    )
                    parts = [part for part in normalized.split() if part]
                    if parts:
                        full_name_guess = " ".join(part.capitalize() for part in parts)

            directory_entry = find_directory_entry(
                username=u.username,
                full_name=full_name or full_name_guess,
                email=u.email,
            )
            display_email = u.email
            if not display_email and directory_entry:
                display_email = directory_entry.get("email", "")
            if not display_email and "@" in (u.username or ""):
                display_email = u.username
            display_label = display_email or u.username
            choices.append((u.username, display_label))

        self.fields["username"].choices = choices
