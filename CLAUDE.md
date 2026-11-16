# CLAUDE.md

## Regras de código

- Não escreva comentários nem docstrings no código (Python, YAML, TOML, INI, Dockerfile). O código deve se explicar por nomes claros e boa estrutura.
- Exceções permitidas, por serem funcionais e não explicativas:
  - diretivas de ferramentas, como `# noqa: F401`, sem texto explicativo junto;
  - o docstring de cabeçalho das migrações do Alembic (`migrations/versions/*.py` e `migrations/script.py.mako`), que o Alembic usa em `alembic history`.
- Ao editar um arquivo, remova comentários que encontrar, respeitando as exceções acima.

## Comandos

- Subir tudo: `docker compose up -d --build`
- Testes: `docker compose run --rm --build tests`
- Lint/format: `docker compose run --rm tests sh -c "ruff check . && ruff format --check ."`
- Nova migração: `docker compose run --rm -v "$PWD/migrations:/code/migrations" migrate alembic revision --autogenerate -m "..."`
