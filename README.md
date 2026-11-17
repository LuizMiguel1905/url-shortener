# Encurtador de URL (FastAPI + Postgres + Alembic)

[![CI](https://github.com/LuizMiguel1905/url-shortener/actions/workflows/ci.yml/badge.svg)](https://github.com/LuizMiguel1905/url-shortener/actions/workflows/ci.yml)

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

## Testes

```bash
docker compose run --rm --build tests
```

Rodam contra um Postgres real, no banco separado `encurtador_test` (criado automaticamente; o
conftest recusa qualquer banco cujo nome não termine em `_test`). O schema é criado pelas próprias
migrações do Alembic, e as tabelas são limpas após cada teste.

- `tests/test_api.py`: rotas HTTP (criação, validação, conflitos, redirecionamento, 404, 503)
- `tests/test_services.py`: regras de negócio (geração de código, retentativas em colisão, cliques)
- `tests/test_migrations.py`: `alembic check` (modelo sem migração falha o teste) e downgrade/upgrade
- `tests/test_pool.py`: mais requisições simultâneas que threads e conexões não pode travar, e toda rota devolve a conexão ao pool

Fora do Docker: `pip install -r requirements-dev.txt` e `pytest` (usa `localhost:5433` por padrão,
ou a variável `TEST_DATABASE_URL`).

## Teste de carga (k6)

```bash
docker compose up -d --build
docker compose --profile load run --rm --service-ports k6
```

O k6 só começa quando a API está saudável. Depois de mudar o código, suba com `--build`: sem ele o
Compose reaproveita a imagem antiga e você mede o código velho.

Durante o teste, o dashboard com gráficos em tempo real fica em http://localhost:5665 (só enquanto ele roda).
Ao final, o relatório é salvo em `loadtest/report.html`.

Mistura 90% de `GET /{code}` e 10% de `POST /links`, com limites de falha (< 1%) e de latência (p95 < 500 ms).
Ajustes por variável de ambiente: `VUS` (padrão 50), `DURATION` (padrão 30s) e `WEB_CONCURRENCY`
(workers do uvicorn na API, padrão 1):

```bash
WEB_CONCURRENCY=4 docker compose up -d --build api
VUS=100 DURATION=2m docker compose --profile load run --rm --service-ports k6
```

Cada worker tem o próprio pool de conexões: o total é `WEB_CONCURRENCY` x (5 + 10) e precisa ficar
abaixo do `max_connections` do Postgres (100 por padrão).

## Estrutura

```
app/
  config.py     configurações (DATABASE_URL, BASE_URL) via env/.env
  database.py   engine, Base (com naming convention) e SessionLocal
  models.py     modelo Link
  schemas.py    entrada/saída da API (Pydantic)
  services.py   regras de negócio (gerar código, criar, resolver) — sem HTTP
  routes.py     rotas FastAPI, abrem e fecham a sessão dentro da rota e traduzem erros de domínio em status HTTP
  main.py       cria o app e registra as rotas
migrations/     Alembic (env.py lê a URL de app.config)
tests/          pytest (conftest cria o banco de teste e aplica as migrações)
loadtest/       script k6
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
