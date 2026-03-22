"""
User directory and role data shared between seeding, login UX, and the settings page.

This module keeps the catalog of SSO identifiers, emails, and profile keys that
match the spreadsheet shared by the business team so it can be rendered consistently
in different parts of the portal.

Note: this is sample/demo data for the public version of the project. The
original internal roster (real names, corporate emails, employee IDs) has
been replaced with fictitious entries.
"""

DEFAULT_PASSWORD_PLACEHOLDER = "changeme123"

PROFILE_KEY_INFO = {
    "admin_dashboard": {
        "group": "ADMIN",
        "label": "Admin",
        "description": "Coordenação",
    },
    "admin_solicitantes": {
        "group": "SOLICITANTE",
        "label": "Solicitante",
        "description": "Engenharia de Processo",
    },
    "admin_projetista": {
        "group": "PROJETISTA",
        "label": "Projetista",
        "description": "Área de Projeto",
    },
    "DISPOSITIVO": {
        "group": "DISPOSITIVOS",
        "label": "Dispositivos",
        "description": "Dispositivos",
    },
}

USER_DIRECTORY = [
    {
        "sso": "100000001",
        "full_name": "Ana Souza",
        "email": "ana.souza@example.com",
        "profile_key": "admin_dashboard",
    },
    {
        "sso": "100000002",
        "full_name": "Bruno Almeida",
        "email": "bruno.almeida@example.com",
        "profile_key": "admin_dashboard",
    },
    {
        "sso": "100000003",
        "full_name": "Carla Ribeiro",
        "email": "carla.ribeiro@example.com",
        "profile_key": "admin_dashboard",
    },
    {
        "sso": "100000004",
        "full_name": "Diego Martins",
        "email": "diego.martins@example.com",
        "profile_key": "admin_solicitantes",
    },
    {
        "sso": "100000005",
        "full_name": "Elaine Costa",
        "email": "elaine.costa@example.com",
        "profile_key": "admin_solicitantes",
    },
    {
        "sso": "100000006",
        "full_name": "Fabio Teixeira",
        "email": "fabio.teixeira@example.com",
        "profile_key": "admin_solicitantes",
    },
    {
        "sso": "100000007",
        "full_name": "Giovana Pires",
        "email": "giovana.pires@example.com",
        "profile_key": "admin_solicitantes",
    },
    {
        "sso": "100000008",
        "full_name": "Hugo Fernandes",
        "email": "hugo.fernandes@example.com",
        "profile_key": "admin_solicitantes",
    },
    {
        "sso": "100000009",
        "full_name": "Isabela Nogueira",
        "email": "isabela.nogueira@example.com",
        "profile_key": "admin_solicitantes",
    },
    {
        "sso": "100000010",
        "full_name": "Joao Cardoso",
        "email": "joao.cardoso@example.com",
        "profile_key": "admin_solicitantes",
    },
    {
        "sso": "100000011",
        "full_name": "Karina Duarte",
        "email": "karina.duarte@example.com",
        "profile_key": "admin_solicitantes",
    },
    {
        "sso": "100000012",
        "full_name": "Lucas Barros",
        "email": "lucas.barros@example.com",
        "profile_key": "admin_solicitantes",
    },
    {
        "sso": "100000013",
        "full_name": "Marina Rocha",
        "email": "marina.rocha@example.com",
        "profile_key": "admin_projetista",
    },
    {
        "sso": "100000014",
        "full_name": "Nicolas Vieira",
        "email": "nicolas.vieira@example.com",
        "profile_key": "admin_projetista",
    },
    {
        "sso": "100000015",
        "full_name": "Otavio Lima",
        "email": "otavio.lima@example.com",
        "profile_key": "admin_projetista",
    },
    {
        "sso": "100000016",
        "full_name": "Patricia Gomes",
        "email": "patricia.gomes@example.com",
        "profile_key": "admin_projetista",
    },
    {
        "sso": "100000017",
        "full_name": "Rafael Moreira",
        "email": "rafael.moreira@example.com",
        "profile_key": "admin_projetista",
    },
    {
        "sso": "100000018",
        "full_name": "Sabrina Freitas",
        "email": "sabrina.freitas@example.com",
        "profile_key": "DISPOSITIVO",
    },
    {
        "sso": "100000019",
        "full_name": "Thiago Correia",
        "email": "thiago.correia@example.com",
        "profile_key": "DISPOSITIVO",
    },
]

USER_DIRECTORY_MAP = {}
for entry in USER_DIRECTORY:
    USER_DIRECTORY_MAP.setdefault(entry["sso"], entry)

def _normalize_value(value: str) -> str:
    return (value or "").strip().lower()

def find_directory_entry(username: str = "", full_name: str = "", email: str = ""):
    """Return the best match from USER_DIRECTORY using the available identifiers."""
    username_value = _normalize_value(username)
    full_name_value = _normalize_value(full_name)
    email_value = _normalize_value(email)

    entries_for_sso = []
    if username_value:
        entries_for_sso = [
            entry for entry in USER_DIRECTORY
            if _normalize_value(entry.get("sso", "")) == username_value
        ]
        if entries_for_sso:
            if full_name_value:
                for entry in entries_for_sso:
                    if _normalize_value(entry.get("full_name", "")) == full_name_value:
                        return entry
            if len(entries_for_sso) == 1:
                return entries_for_sso[0]

    if email_value:
        for entry in USER_DIRECTORY:
            if _normalize_value(entry.get("email", "")) == email_value:
                return entry

    if full_name_value:
        for entry in USER_DIRECTORY:
            if _normalize_value(entry.get("full_name", "")) == full_name_value:
                return entry

    if username_value and not username_value.isdigit():
        prefix_matches = [
            entry for entry in USER_DIRECTORY
            if _normalize_value(entry.get("full_name", "")).startswith(username_value)
        ]
        if len(prefix_matches) == 1:
            return prefix_matches[0]

    if entries_for_sso:
        return entries_for_sso[0]

    return None

def get_display_profile(profile_key: str) -> str:
    """Return the human-friendly label for the provided profile key."""
    info = PROFILE_KEY_INFO.get(profile_key, {})
    return info.get("label", profile_key)

def get_group_for_profile(profile_key: str) -> str:
    """Return the GROUP code mapped to the profile key for seeding."""
    return PROFILE_KEY_INFO.get(profile_key, {}).get("group", "")
