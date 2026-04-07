# Auth

A complete OAuth 2.0 authentication service built with Python and FastAPI. Supports login via Google, Microsoft, Okta, and GitHub. Sessions are managed with signed JWT cookies — no database required.

> **This entire repository was generated from a single [`auth.dai`](./auth.dai) file using [DAI Studio](https://dai.studio).** The `.dai` file is a workflow blueprint that describes the service's architecture, API endpoints, dependencies, rules, and tests. An AI coding agent read it and produced every line of code you see here. See [How it was built](#how-it-was-built) for more.

---

## Features

- OAuth 2.0 login for **Google**, **Microsoft**, **Okta**, and **GitHub**
- Stateless sessions via **signed JWT in an HttpOnly cookie** (no Redis, no DB)
- Single `main.py` — simple and easy to follow
- 12-factor config — all secrets via environment variables
- Conda environment managed with `environment.yml`
- `Makefile` for common tasks
- Docker support for local container builds
- E2E test suite with pytest

---

## Project structure

```
auth/
├── auth.dai            # Workflow blueprint (source of truth)
├── main.py             # FastAPI application
├── environment.yml     # Conda environment definition
├── .env.example        # Environment variable template
├── Makefile            # Developer task runner
├── Dockerfile          # Container build
└── tests/
    └── test_routes.py  # E2E route tests
```

---

## Getting started

### Prerequisites

- [Conda](https://docs.conda.io/en/latest/miniconda.html)
- OAuth app credentials for the providers you want to use (Google, Microsoft, Okta, GitHub)

### 1. Clone and set up the environment

```bash
git clone <repo-url>
cd auth
make setup          # creates the 'auth' conda environment
conda activate auth
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
# Required — used to sign JWT session cookies
SECRET_KEY=your-long-random-secret

# At least one OAuth provider
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
MICROSOFT_TENANT_ID=common

OKTA_CLIENT_ID=...
OKTA_CLIENT_SECRET=...
OKTA_DOMAIN=your-tenant.okta.com

GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...

# Where the server is reachable (used to build redirect URIs)
BASE_URL=http://localhost:8000
```

Each provider requires you to register an OAuth app and add the corresponding callback URL:

| Provider  | Callback URL                          |
|-----------|---------------------------------------|
| Google    | `http://localhost:8000/auth/google/return`    |
| Microsoft | `http://localhost:8000/auth/microsoft/return` |
| Okta      | `http://localhost:8000/auth/okta/return`      |
| GitHub    | `http://localhost:8000/auth/github/return`    |

### 3. Start the server

```bash
make start
```

Open `http://localhost:8000` in your browser. The root page shows your login state and links to each provider.

---

## API routes

| Method | Path                    | Description                                      |
|--------|-------------------------|--------------------------------------------------|
| GET    | `/`                     | Shows whether you are logged in                  |
| GET    | `/auth/google/login`    | Redirects to Google OAuth                        |
| GET    | `/auth/google/return`   | Handles Google callback, sets session cookie     |
| GET    | `/auth/microsoft/login` | Redirects to Microsoft OAuth                     |
| GET    | `/auth/microsoft/return`| Handles Microsoft callback, sets session cookie  |
| GET    | `/auth/okta/login`      | Redirects to Okta OAuth                          |
| GET    | `/auth/okta/return`     | Handles Okta callback, sets session cookie       |
| GET    | `/auth/github/login`    | Redirects to GitHub OAuth                        |
| GET    | `/auth/github/return`   | Handles GitHub callback, sets session cookie     |
| GET    | `/auth/logout`          | Clears session cookie, redirects to `/`          |

---

## Development

```bash
make test       # run the test suite
make format     # format code with black
make start      # start the dev server with --reload
```

### Docker

```bash
docker build -t auth .
docker run --env-file .env -p 8000:8000 auth
```

---

## How it was built

This repository is an example of **specification-driven code generation** using [DAI Studio](https://dai.studio).

The workflow starts with a single file — [`auth.dai`](./auth.dai). This is a `.dai` file: a BPMN-based workflow diagram extended with DAI Studio's schema. It encodes not just a flowchart, but a structured machine-readable specification:

- **API endpoints** — paths, auth types, and descriptions for every route
- **Services** — the central `Authenticate` service and how all providers flow into it
- **Dependencies** — Python 3.14, FastAPI, Authlib, Conda, black, Make, Docker — with versions and purposes
- **Rules** — hard constraints like "minimalistic", "12-factor", and "simple" that the AI must enforce globally
- **Tests** — an e2e test case specifying what to validate and how to determine pass/fail
- **CI/CD context** — build target and Docker dependency

A DAI Studio workflow loaded this `.dai` file and passed it to an AI coding agent. The agent read the spec and produced the entire codebase — `main.py`, `environment.yml`, `Makefile`, `Dockerfile`, `.env.example`, and `tests/` — with no additional instructions beyond what was encoded in the diagram.

To build your own app this way, visit [dai.studio](https://dai.studio).
