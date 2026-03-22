"""
WSGI config for config project.

WSGI (Web Server Gateway Interface) é a interface padrão entre servidores web
e aplicações Python, usada em produção.

Este arquivo expõe a variável `application` que é chamada pelo servidor web
(como Gunicorn, uWSGI, etc) para processar requisições HTTP.

Documentação: https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/

Uso em produção com Gunicorn:
    gunicorn config.wsgi --bind 0.0.0.0:8000
"""

import os

from django.core.wsgi import get_wsgi_application

# Define qual arquivo de configurações usar
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Obtém a aplicação WSGI do Django
# Esta é a variável que o servidor web vai chamar
application = get_wsgi_application()

