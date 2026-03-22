"""Template filters utilitários para trabalhar com dicionários no template do Django.

Inclui filtros pequenos e seguros que facilitam a leitura de chaves dinâmicas
em mappings sem causar erros no template.
"""

from django import template

register = template.Library()


@register.filter
def dict_item(mapping, key):
    """Return mapping[key] while keeping template syntax valid for dynamic keys."""
    if mapping is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return None
