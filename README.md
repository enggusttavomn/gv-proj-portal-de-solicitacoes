# GV_PROJ

Sistema Django com perfis de acesso (Admin, Solicitante e Projetista), dashboards e fluxo de solicitações.

## Requisitos

- Windows 10/11
- Python 3.12+ (recomendado 3.12 ou 3.13)
- Git

## Subindo em outra máquina

1. Clone o repositório:

```powershell
git clone <URL_DO_REPOSITORIO>
cd GV_PROJ
```

2. Crie e ative o ambiente virtual:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Instale dependências:

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

4. Aplique as migrations:

```powershell
python manage.py migrate
```

5. Popule dados iniciais (opcional):

```powershell
python seed_users.py
python seed_solicitacoes.py
```

6. Rode os servidores:

```powershell
.\GUSTAVO_run_three_servers_local.bat
```

## URLs

- Admin: http://127.0.0.1:8000/accounts/login
- Solicitante: http://127.0.0.2:8001/accounts/login
- Projetista: http://127.0.0.3:8002/accounts/login

## Observações

- O arquivo `db.sqlite3` está versionado para facilitar o uso imediato.
- Os scripts `.bat` tentam detectar automaticamente `.venv_local`, `.venv2` ou `.venv`.
- Para uso público no GitHub, revise segredos e dados sensíveis antes de publicar.
