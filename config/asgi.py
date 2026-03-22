"""
ASGI config for config project.

ASGI (Asynchronous Server Gateway Interface) é a interface para aplicações
assíncronas Python, permitindo suporte a WebSockets e async/await.

Este arquivo expõe a variável `application` que é chamada pelo servidor ASGI
(como Daphne, Hypercorn, etc).

Documentação: https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/

Nota: Em desenvolvimento, use WSGI com manage.py runserver
Em produção com suporte a async, use ASGI com Daphne ou Hypercorn:
    daphne -b 0.0.0.0 -p 8000 config.asgi:application
"""

import os

from django.core.asgi import get_asgi_application

# Define qual arquivo de configurações usar
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Obtém a aplicação ASGI do Django
# Esta é a variável que o servidor ASGI vai chamar
application = get_asgi_application()

