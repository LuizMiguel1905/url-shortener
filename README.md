# Encurtador de URL (FastAPI + Postgres + Alembic)

## Rodando

```bash
docker compose up -d --build
```

Sobe três serviços: `db` (Postgres, porta 5433), `migrate` (roda `alembic upgrade head` e encerra) e `api` (porta 8000, só inicia se as migrações passarem).
Docs interativas: http://localhost:8000/docs

## Rotas

### `POST /links` — cria um link curto

```bash
curl -X POST localhost:8000/links -H 'Content-Type: application/json' \
  -d '{"url": "https://fastapi.tiangolo.com"}'
# opcional: "custom_code": "fastapi"  (3-32 caracteres: letras, números, _ e -)
```

- `201` com `code`, `short_url`, `target_url`, `clicks`, `created_at`
- `409` se o `custom_code` já existir ou for reservado (`docs`, `redoc`, `links`)
- `422` se a URL for inválida

### `GET /{code}` — redireciona

`307` para a URL original, incrementando `clicks`. `404` se o código não existir.

## Migrações (Alembic)

O schema é gerenciado só pelo Alembic; a aplicação não cria tabelas.

```bash
# depois de alterar app/models.py, gerar uma nova migração:
docker compose run --rm -v "$PWD/migrations:/code/migrations" migrate \
  alembic revision --autogenerate -m "descricao da mudanca"

docker compose run --rm migrate alembic upgrade head     # aplicar
docker compose run --rm migrate alembic downgrade -1     # desfazer a última
docker compose run --rm migrate alembic check            # modelos x banco em sincronia?
```

Revise sempre o arquivo gerado em `migrations/versions/` antes de aplicar.

## Estrutura

```
app/
  config.py     configurações (DATABASE_URL, BASE_URL) via env/.env
  database.py   engine, Base (com naming convention), sessão e dependência DbSession
  models.py     modelo Link
  schemas.py    entrada/saída da API (Pydantic)
  services.py   regras de negócio (gerar código, criar, resolver) — sem HTTP
  routes.py     rotas FastAPI, traduz erros de domínio em status HTTP
  main.py       cria o app e registra as rotas
migrations/     Alembic (env.py lê a URL de app.config)
```

## Rodando fora do Docker

Precisa do pacote `python3.12-venv` no sistema.

```bash
cp .env.example .env
docker compose up -d db
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head                 # usa DATABASE_URL do .env (localhost:5433)
uvicorn app.main:app --reload
```
