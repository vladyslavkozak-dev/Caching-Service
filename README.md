# payload-cache

A FastAPI service that builds payloads from two lists of strings. Every string goes through a
slow "transformer" (a stand-in for an external service), and the results are cached in
PostgreSQL so the transformer is called as rarely as possible. `cache-cli` is a small client
for exercising the service from the command line.

## Quick start

Requires Docker with the Compose plugin.

```bash
docker compose up --build -d --wait

curl -s -X POST localhost:8000/payload \
  -H 'Content-Type: application/json' \
  -d @examples/sample.json
# {"id":"a852dc89-d893-48d4-8ecf-0f2f1d19a7ae","message":"Payload created"}

curl -s localhost:8000/payload/a852dc89-d893-48d4-8ecf-0f2f1d19a7ae
# {"output":"FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"}
```

The CLI is installed in the image too, so it can be tried without a local Python setup:

```bash
docker compose exec api cache-cli -r 3 \
  -j '{"list_1": ["first string", "second string"], "list_2": ["other string", "last string"]}'
```

Interactive API docs are at http://localhost:8000/docs. Stop everything with
`docker compose down` (add `-v` to also drop the database volume).

## How it works

### Payload generation

The input is two lists of the same length. Each string is transformed (upper-cased after an
artificial delay, `TRANSFORM_DELAY` seconds), then the results are interleaved,
`list_1[0], list_2[0], list_1[1], list_2[1], ...`, and joined with `", "`.

### Caching

Caching happens on two levels, both in PostgreSQL:

| Table                 | Key                        | Stores                         |
|-----------------------|----------------------------|--------------------------------|
| `payloads`            | `id` (UUID), `input_hash` (unique) | the generated `output` |
| `transformed_strings` | `source` (the input string) | the transformer's `result`    |

`POST /payload` goes through these steps (`src/payload_cache/service.py`):

1. Hash the input (SHA-256 of `[list_1, list_2]` as JSON, so list boundaries and order
   matter). If a payload with this hash exists, return its id. The transformer is not
   called at all.
2. Collect the unique strings from both lists and load the cached ones in a single query.
3. Call the transformer only for strings that are not cached yet. Duplicates inside one
   request are transformed once.
4. Store the new transformations and the payload, then return the new id.

So a payload that shares some strings with earlier ones only pays for the new strings, and a
repeated payload costs a single indexed lookup.

### Transactions and concurrency

- The read transaction is committed before the transformer is called, so a request waiting
  on the slow service doesn't hold a pooled connection. Without that, 16 concurrent uncached
  requests exhausted the default pool (5 + 10 overflow) and one failed with a pool timeout
  (`test_transaction_is_closed_while_transforming`).
- Both inserts use `ON CONFLICT DO NOTHING`. When two identical requests race, the database
  keeps one payload and both requests get its id
  (`test_concurrent_identical_requests_share_payload`).
- New strings are inserted in sorted order. Concurrent requests with overlapping strings then
  take row locks in the same order, which rules out deadlocks
  (`test_concurrent_overlapping_payloads_do_not_deadlock`).

Known limitation: two *concurrent* requests that share a string that isn't cached yet will
both call the transformer for it. The results are identical and only one is stored. Avoiding
it would need a lock per string (for example Postgres advisory locks), which wasn't worth the
complexity here.

## API

### `POST /payload`

```json
{
  "list_1": ["first string", "second string", "third string"],
  "list_2": ["other string", "another string", "last string"]
}
```

| Status | When | Body |
|--------|------|------|
| `201`  | new payload | `{"id": "a852dc89-...", "message": "Payload created"}` |
| `200`  | the same input was posted before | `{"id": "a852dc89-...", "message": "Payload already exists"}` |
| `422`  | invalid input | FastAPI validation error |

Input rules: both lists are required, non-empty, and of the same length. Each item is a string
of at most 500 characters (see [Decisions](#decisions-and-shortcuts)) without NUL characters,
which Postgres text columns can't store.

```bash
curl -s -X POST localhost:8000/payload -H 'Content-Type: application/json' \
  -d '{"list_1": ["a"], "list_2": ["b", "c"]}'
# {"detail":[{"type":"value_error","loc":["body"],"msg":"Value error, list_1 and list_2 must have the same length", ...}]}
```

### `GET /payload/{id}`

| Status | When | Body |
|--------|------|------|
| `200`  | payload exists | `{"output": "FIRST STRING, OTHER STRING, ..."}` |
| `404`  | unknown id | `{"detail": "Payload not found"}` |
| `422`  | id is not a UUID | FastAPI validation error |

## CLI

```
cache-cli [-h|--host URL] [-r|--repeat N] [-i|--input FILE|-] [-j|--json JSON] [-o|--output FILE|-] [--help]
```

| Option | Default | Meaning |
|--------|---------|---------|
| `-h`, `--host` | `http://localhost:8000` | service URL, `http` or `https` |
| `-r`, `--repeat` | `1` | number of iterations, a positive integer |
| `-i`, `--input` | | file with a JSON payload, `-` for stdin |
| `-j`, `--json` | | JSON payload passed directly |
| `-o`, `--output` | `-` | file for results, `-` for stdout |
| `--help` | | show help |

Exactly one of `--input` and `--json` is required. Arguments are parsed and validated with
Pydantic Settings (`src/cache_cli/settings.py`). The payload is checked against the same schema
the service uses before any request is sent. Environment variables are deliberately ignored, so a
stray `HOST` in the shell can't redirect the tool.

Each iteration does a `POST` followed by a `GET` and writes one JSON line:

```bash
cache-cli -r 3 -i examples/sample.json
# {"iteration": 1, "id": "a852dc89-...", "created": true, "output": "FIRST STRING, ...", "elapsed_ms": 3045.7}
# {"iteration": 2, "id": "a852dc89-...", "created": false, "output": "FIRST STRING, ...", "elapsed_ms": 8.3}
# {"iteration": 3, "id": "a852dc89-...", "created": false, "output": "FIRST STRING, ...", "elapsed_ms": 5.3}
```

The first iteration pays for six transformer calls (6 × 0.5 s by default), the next ones are
served from the cache. Other examples:

```bash
cat examples/sample.json | cache-cli -i - -o results.jsonl
cache-cli -h http://localhost:8000 -j '{"list_1": ["a"], "list_2": ["b"]}'
python -m cache_cli --help
```

Exit codes: `0` on success, `2` for invalid arguments or payload, `1` if the server is
unreachable or returns an error.

## Local development

Requires Python 3.10+ and PostgreSQL. Docker is only needed for the Compose setup.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Create a database user and two databases, one for running the service and one for tests:

```bash
sudo -u postgres psql -c "CREATE USER cache WITH PASSWORD 'cache';"
sudo -u postgres psql -c "CREATE DATABASE cache OWNER cache;"
sudo -u postgres psql -c "CREATE DATABASE cache_test OWNER cache;"
```

Run the service (tables are created on startup):

```bash
cp .env.example .env
.venv/bin/uvicorn payload_cache.main:app --reload
```

### Configuration

| Variable | Default | Used by |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+psycopg://cache:cache@localhost:5432/cache` | service |
| `TRANSFORM_DELAY` | `0.5` | service, seconds per transformer call |
| `TEST_DATABASE_URL` | unset | integration tests |

The Compose file doesn't publish the database port, so it doesn't clash with a PostgreSQL
already running on the host.

## Tests

```
tests/
  unit/          no database: interleaving, hashing, schemas, CLI parsing and output
  integration/   real PostgreSQL: service, HTTP API, CLI against the app
```

Integration tests need `TEST_DATABASE_URL` and are skipped without it. **The tests truncate
the tables**, so point it at a dedicated database.

```bash
# against the local PostgreSQL set up above
TEST_DATABASE_URL=postgresql+psycopg://cache:cache@localhost:5432/cache_test .venv/bin/pytest -v

# or against a throwaway container
docker run -d --rm --name payload-cache-test -p 5433:5432 \
  -e POSTGRES_USER=cache -e POSTGRES_PASSWORD=cache -e POSTGRES_DB=cache_test postgres:16
TEST_DATABASE_URL=postgresql+psycopg://cache:cache@localhost:5433/cache_test .venv/bin/pytest -v
docker stop payload-cache-test

# unit tests only
.venv/bin/pytest tests/unit
```

The transformer is replaced with a call-counting fake in the tests, so they assert the exact
number of transformer calls rather than timing.

Linting and formatting:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

## Project layout

```
src/payload_cache/
  main.py          app factory, engine and table creation on startup
  api.py           endpoints and the transformer dependency
  service.py       payload generation and caching logic
  schemas.py       request and response models
  models.py        SQLAlchemy tables
  transformer.py   the simulated external service
  db.py            per-request session
  config.py        settings from the environment
src/cache_cli/
  settings.py      argument parsing and validation
  client.py        HTTP client for the two endpoints
  main.py          input/output handling and the iteration loop
```

## Decisions and shortcuts

- **No migrations.** Tables are created with `metadata.create_all` on startup. The schema
  has two tables and has never changed. Alembic would be the next step before any schema
  change.
- **Strings are limited to 500 characters.** Each string is the primary key of the cache
  table, and a Postgres B-tree entry can't exceed about 2.7 KB. 500 characters fits even with
  4-byte UTF-8 characters. Keying the cache by a hash of the string would lift the limit.
- **The generated output is stored** with the payload, so `GET` is a single primary-key lookup
  and doesn't depend on the cache table.
- **Synchronous SQLAlchemy.** FastAPI runs sync endpoints in a thread pool, so a slow
  transformer call doesn't block the event loop. It also keeps the code simpler than async.
- **Single-layer Docker build.** Dependencies and code are installed in one `pip install .`
  step, so code changes reinstall dependencies. That's fine at this size.

## Known limitations

- **Transformation happens inside the `POST` request.** A payload with many new strings takes
  `TRANSFORM_DELAY` seconds per string before it responds, and `cache-cli` gives up after 60
  seconds. The server still finishes and caches the result, so a retry is fast. A production
  version would hand the work to a queue and let the client poll.
- **Concurrent requests may transform the same new string twice**, see
  [Transactions and concurrency](#transactions-and-concurrency).
- **Lone surrogates such as `"\ud800"` get a `500` instead of a `422`.** Pydantic rejects
  them, but FastAPI's default validation error response echoes the input back and fails to
  encode it as UTF-8. Fixing it means replacing the default error handler.
- **One worker.** `create_all` on startup isn't safe to run from several workers at once.
  With migrations run as a separate step, `uvicorn --workers N` would work.
- **No authentication or rate limiting.**

## Open questions about the spec

- The spec uses `-h` for both `--host` and `--help`. Here `-h` is `--host`, and help is only
  `--help`.
- The spec mentions "payload files". Payloads are stored as database rows rather than files,
  since they are small strings and requirement 4 already asks for a database.
- Empty lists are rejected with `422`. The spec doesn't say whether an empty payload is valid.
- A repeated `POST` returns `200` instead of `201`, so a client can tell a new payload from an
  existing one.
