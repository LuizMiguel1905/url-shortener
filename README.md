# Encurtador de URL (FastAPI + Postgres + Alembic)

[![CI](https://github.com/LuizMiguel1905/url-shortener/actions/workflows/ci.yml/badge.svg)](https://github.com/LuizMiguel1905/url-shortener/actions/workflows/ci.yml)

## Rodando

```bash
docker compose up -d --build
```

Sobe quatro serviços: `db` (Postgres, porta 5433), `redis` (cache, porta 6380), `migrate` (roda `alembic upgrade head` e encerra) e `api` (porta 8000, só inicia se as migrações passarem e o Redis estiver saudável).
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

`307` para a URL original. `404` se o código não existir. Os `clicks` são contados no Redis e gravados no banco em lote (a cada 5 s por padrão), então o valor no banco é eventualmente consistente.

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
- `tests/test_cache.py`: cache-aside (hit, miss, TTL), contagem de cliques em lote e comportamento com o Redis fora do ar
- `tests/test_pool.py`: mais requisições simultâneas que threads e conexões não pode travar, e toda rota devolve a conexão ao pool

Fora do Docker: `docker compose up -d db redis`, `pip install -r requirements-dev.txt` e `pytest` (usa
`localhost:5433` e `localhost:6380/1` por padrão, ou as variáveis `TEST_DATABASE_URL` e `TEST_REDIS_URL`).
O Redis de teste precisa usar um banco diferente do 0, porque os testes limpam o banco inteiro dele.

## Cache (Redis)

O redirecionamento é o caminho quente: muitas leituras e uma escrita (o contador de cliques) por requisição.

- **Cache-aside na leitura:** `GET /{code}` procura `link:{code}` no Redis. Em caso de miss, lê o Postgres e grava no Redis com TTL.
- **Write-through na criação:** `POST /links` já grava o link no cache, então o primeiro clique é um hit.
- **TTL:** `CACHE_TTL_SECONDS` (padrão 3600). Os links são imutáveis, então o TTL serve para liberar memória. Se um dia existir edição ou remoção, a invalidação é apagar a chave `link:{code}` no mesmo fluxo.
- **Cliques em lote (write-behind):** cada clique faz `INCR clicks:{code}` no Redis, e uma tarefa em segundo plano (`CLICKS_FLUSH_INTERVAL_SECONDS`, padrão 5) soma os acumulados no Postgres. Sem isso o cache de leitura não traria ganho, porque cada redirecionamento ainda faria um `UPDATE`.
- **Redis fora do ar:** a API continua funcionando, lendo e contando direto no Postgres (mais lenta, sem perder cliques). Os timeouts do Redis são curtos (0,2 s) para a falha não segurar as requisições.
- **Trade-off:** o Redis roda sem persistência, então uma queda dele pode perder os cliques ainda não gravados (até ~5 s). Para contagem de cliques isso costuma ser aceitável; para dados que não podem se perder, ative AOF ou use uma fila.

Medição indicativa (k6, 50 VUs, 20 s, 1 worker, tudo na mesma máquina de 2 núcleos, 90% `GET`, 10% `POST`):

| Versão | req/s | média | p95 |
| --- | --- | --- | --- |
| Sem cache | ~440 | 113 ms | ~211 ms |
| Cache só na leitura, clique direto no banco | ~435 | 115 ms | ~208 ms |
| Cache + cliques em lote | ~1130 | 44 ms | ~101 ms |

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
  config.py     configurações (DATABASE_URL, REDIS_URL, BASE_URL, TTL do cache) via env/.env
  cache.py      cliente Redis e operações de cache e de contagem de cliques (tolera Redis fora do ar)
  database.py   engine, Base (com naming convention) e SessionLocal
  models.py     modelo Link
  schemas.py    entrada/saída da API (Pydantic)
  services.py   regras de negócio (gerar código, criar, buscar URL, somar cliques) — sem HTTP
  redirects.py  caminho quente do redirecionamento: cache-aside e envio dos cliques ao banco
  routes.py     rotas FastAPI, abrem e fecham a sessão dentro da rota e traduzem erros de domínio em status HTTP
  main.py       cria o app, registra as rotas e roda a tarefa que grava os cliques
migrations/     Alembic (env.py lê a URL de app.config)
tests/          pytest (conftest cria o banco de teste e aplica as migrações)
loadtest/       script k6
```

## Rodando fora do Docker

Precisa do pacote `python3.12-venv` no sistema.

```bash
cp .env.example .env
docker compose up -d db redis
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head                 # usa DATABASE_URL do .env (localhost:5433)
uvicorn app.main:app --reload
```
