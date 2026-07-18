# my-finance

Personal expense tracker with three services:

- **backend** — FastAPI + SQLite (`backend/`)
- **receipt_parser** — FastAPI + local Qwen model that extracts data from receipt images (`receipt_parser/`)
- **frontend** — Vite/React SPA served by nginx (`frontend/`)

## Deployment (`deploy.sh`)

`deploy.sh` is the single entry point for building and running the stack. It
wraps `docker compose` and loads environment variables from `envs/<env>.env`.

### Prerequisites

- Docker with Compose v2 (`docker compose`) — v1 (`docker-compose`) also works.
- The Qwen model weights present at
  `receipt_parser/app/data/models/Qwen3.5-2B/` (mounted read-only into the
  `receipt_parser` container; see [docker-compose.yml](docker-compose.yml)).

### Usage

```bash
./deploy.sh --env <local|prod> [--down | --logs]
```

| Flag        | Effect                                                      |
| ----------- | ----------------------------------------------------------- |
| `--env`     | **Required.** Target environment. Only `local` is implemented today; `prod`/`aws` exits with a "not implemented" message. |
| `--down`    | Stop and remove the local containers.                       |
| `--logs`    | Follow logs from all local containers.                      |
| `-h`, `--help` | Print usage.                                             |

Default action (no flag) is `up --build -d`.

### Local environment

```bash
# Build images and start the stack in the background
./deploy.sh --env local

# Follow logs
./deploy.sh --env local --logs

# Tear it down
./deploy.sh --env local --down
```

On a successful `up`, the script prints the URLs it just brought up, e.g.:

```
Local stack is up:
  frontend        http://localhost:8501
  backend API     http://localhost:8000
  receipt parser  http://localhost:8001
```

Host ports come from [envs/local.env](envs/local.env) — change
`FRONTEND_PORT` / `BACKEND_PORT` / `RECEIPT_PARSER_PORT` there if you need
different values.

### Environment files (`envs/`)

`deploy.sh` reads variables from `envs/<env>.env` and uses them in two ways:

1. **Compose variable substitution** — passed via `docker compose --env-file`,
   so `${BACKEND_PORT}` etc. in [docker-compose.yml](docker-compose.yml)
   resolve at compose-time (host port bindings, build args like
   `VITE_BACKEND_URL`).
2. **Container runtime environment** — each service in the compose file
   references the same file via `env_file:`, so the vars are also available
   inside the running containers (e.g. `DATABASE_URL`, `RECEIPT_PARSER_URL`
   for the backend).

`BACKEND_PORT`, `RECEIPT_PARSER_PORT`, and `FRONTEND_PORT` are required —
`deploy.sh` exits with an error if any of them is missing from the env file.

Two env files ship with the repo:

- [envs/local.env](envs/local.env) — everything on localhost / on-disk paths.
- [envs/aws.env](envs/aws.env) — shape only, populated from Terraform outputs.
  Not wired into `deploy.sh` yet (see below).

### `--env prod` / `--env aws`

Not implemented. The script currently exits with status `2` and a "not
implemented yet" message. The intended flow (documented in the header of
[deploy.sh](deploy.sh)) is:

- **frontend** — `npm run build` + `terragrunt apply` to upload `dist/` to S3.
- **backend / receipt_parser** — `docker build` → push to ECR →
  `aws ecs update-service --force-new-deployment`.
