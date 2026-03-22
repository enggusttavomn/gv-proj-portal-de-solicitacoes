def role_context(request):
    user = getattr(request, "user", None)
    role_label = ""
    if user and user.is_authenticated:
        if user.is_superuser or user.groups.filter(name="ADMIN").exists():
            role_label = "Admin"
        elif user.groups.filter(name="DISPOSITIVOS").exists():
            role_label = "Dispositivos"
        elif user.groups.filter(name="PROJETISTA").exists():
            role_label = "Projetista"
        elif user.groups.filter(name="SOLICITANTE").exists():
            role_label = "Solicitante"
        else:
            role_label = "Usuario"

    show_version_switch = role_label in {"Projetista", "Solicitante"}

    return {
        "role_label": role_label,
        "show_version_switch": show_version_switch,
    }
