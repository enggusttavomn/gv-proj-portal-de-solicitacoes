#!/usr/bin/env python
"""
Django's command-line utility for administrative tasks.

Este é o script principal para gerenciar o projeto Django via linha de comando.

Exemplos de uso:
    python manage.py runserver              # Inicia o servidor de desenvolvimento
    python manage.py migrate                # Aplica as migrations no banco
    python manage.py makemigrations         # Cria novas migrations
    python manage.py createsuperuser        # Cria um superusuário
    python manage.py shell                  # Abre o shell Python do Django
    python manage.py collectstatic          # Coleta arquivos estáticos
    python manage.py test                   # Executa os testes
"""
import os
import sys


def main():
    """
    Função principal que executa as tarefas administrativas do Django.
    
    Configuração:
    1. Define o módulo de configurações (config.settings)
    2. Importa o executor de comandos do Django
    3. Processa os argumentos da linha de comando
    
    Args:
        sys.argv: Argumentos passados na linha de comando
    """
    # Define qual arquivo de configuração usar
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    
    try:
        # Importa o executor de comandos do Django
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        # Se Django não estiver instalado, mostra mensagem de erro
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    
    # Executa o comando passado via linha de comando
    execute_from_command_line(sys.argv)


# Ponto de entrada do script
if __name__ == "__main__":
    main()

