# Social Network Pathfinding Engine

[![CI](https://github.com/vivek-pippalla/social-network-pathfinding/actions/workflows/ci.yml/badge.svg)](https://github.com/vivek-pippalla/social-network-pathfinding/actions/workflows/ci.yml)

A production-grade backend that computes the **shortest connection path** between users in a social graph — the same idea as LinkedIn's *"You and Satya Nadella are 3 degrees apart."*

Built with **FastAPI**, **Neo4j**, and **Redis**, seeded with the real-world [Stanford SNAP Facebook dataset](https://snap.stanford.edu/data/ego-Facebook.html) (4,039 users · 88,234 connections). Secured with **JWT authentication** and ships with a **live graph visualization** at `http://localhost:5000`.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [API Endpoints](#api-endpoints)
- [Authentication](#authentication)
- [Graph Visualization](#graph-visualization)
- [Getting Started](#getting-started)
- [Running Tests](#running-tests)
- [Performance](#performance)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)

---

## Overview

Given two user IDs, the engine finds the shortest path through the social graph using Neo4j's built-in **bidirectional BFS** (`shortestPath()`). Results are cached in Redis so repeated queries return in under 10 ms.

The system also provides a **"People You May Know"** endpoint — ranking friend-of-friend suggestions by mutual friend count using the Triadic Closure algorithm — available both as a public endpoint and as a personalized `/me` variant that reads your identity from the JWT.

---

## Features

| Feature | Detail |
|---|---|
| **Shortest Path** | Minimum hops between any two users via Neo4j bidirectional BFS |
| **Redis Caching** | Cache-aside with order-independent keys; ~150 ms → sub-10 ms on cache hits |
| **Friend Suggestions** | Public (`/suggestions/{user_id}`) and personalized (`/suggestions/me`) via JWT |
| **Friend Management** | Add and remove connections (`POST`/`DELETE /friends/{friend_id}`) |
| **Profile Management** | View and update your own profile; view any user's public profile |
| **JWT Authentication** | Register/login flow; protected endpoints require a Bearer token |
| **Graph Visualization** | Interactive vis.js demo at `http://localhost:5000` |
| **Layered Architecture** | Strict Router → Service → Repository → DB separation |
| **Containerized** | Docker Compose with health-check-based startup ordering |
| **Structured Logging** | JSON-formatted logs across all layers |
| **CI Pipeline** | GitHub Actions runs the full test suite on every push |

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI + Pydantic v2 |
| Graph Database | Neo4j 5.12 |
| Caching | Redis 7 |
| Authentication | JWT (python-jose) + bcrypt (passlib) |
| Containerization | Docker + Docker Compose |
| Testing | pytest + httpx |
| Language | Python 3.11 |

---

## Architecture

### High-Level Design

```
Client (Browser / Postman / Swagger)
            │
            ▼ HTTP/REST  (port 5000)
    ┌───────────────────┐
    │   FastAPI Server  │
    │  (JWT on writes)  │
    └───────┬───────────┘
            │
     ┌──────┴──────┐
     ▼             ▼
 Redis Cache    Neo4j Graph DB
 (Cache-Aside)  (Source of Truth)
```

### Request Flow — Pathfinding

```
GET /distance/{start}/{end}   [no auth required]
        │
        ▼
  routes_graph.py  (Router Layer)
        │
        ▼
  pathfinder.py    (Service Layer)
        │
        ├── 1. Build order-independent key: path:min(a,b):max(a,b)
        │
        ├── 2. redis_cache.get(key)
        │        │
        │   ┌────┴────┐
        │   HIT       MISS
        │   │         │
        │ cached=True  graph_repo.find_shortest_path()
        │             │  Neo4j bidirectional BFS
        │             │
        │         redis_cache.set(key, result, ttl=3600)
        │
        └──▶ PathResponse JSON
```

### 4-Tier Internal Architecture

```
app/api/           →   Receive & validate HTTP requests
app/services/      →   Business logic + cache orchestration
app/repositories/  →   Raw Cypher / Redis queries
app/db/            →   Driver & client singletons
```

---

## API Endpoints

### Public (no token required)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/auth/register` | Create account, receive JWT |
| `POST` | `/api/v1/auth/token` | Login (OAuth2 form), receive JWT |
| `GET` | `/distance/{user1}/{user2}` | Shortest path between two users (Redis-cached) |
| `GET` | `/suggestions/{user_id}` | Friend suggestions for any user (ranked by mutual friends) |
| `GET` | `/profile/{user_id}` | Any user's public profile |
| `GET` | `/profile/search?q=` | Search users by name (case-insensitive) |

### Protected (Bearer token required)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/suggestions/me` | Personalized friend suggestions (user ID from JWT) |
| `GET` | `/profile/me` | Your own profile |
| `PUT` | `/profile/me` | Update your name and/or email |
| `POST` | `/friends/{friend_id}` | Add a friend connection |
| `DELETE` | `/friends/{friend_id}` | Remove a friend connection |

### Example — Shortest Path

**Request (no auth needed):**
```
GET /distance/0/150
```

**Response:**
```json
{
  "start_user": "0",
  "end_user": "150",
  "path": ["0", "107", "150"],
  "hops": 2,
  "cached": false
}
```

Run it again — `cached` becomes `true` and latency drops from ~150 ms to < 10 ms.

### Example — Friend Suggestions

**Request (no auth needed):**
```
GET /suggestions/0
```

**Response:**
```json
{
  "user_id": "0",
  "suggestions": [
    { "user_id": "348", "mutual_friends": 12 },
    { "user_id": "414", "mutual_friends": 9 }
  ]
}
```

### Example — Add Friend

**Request (JWT required):**
```
POST /friends/107
Authorization: Bearer <your-token>
```

**Response:**
```json
{ "message": "You are now connected with user '107'." }
```

---

## Authentication

The API uses **JWT Bearer token** authentication for write operations and personalized endpoints. Read-only graph exploration is public.

### Design Principle

> Public endpoints = read-only exploration (no friction for demos and API consumers).  
> Protected endpoints = anything that writes to the graph or returns personalized data.

### Flow

```
1. Register:  POST /api/v1/auth/register  →  { access_token, token_type }
2. Login:     POST /api/v1/auth/token     →  { access_token, token_type }
3. Use:       Authorization: Bearer <access_token>
```

### Quick start with curl

```bash
# 1. Register and capture the token
TOKEN=$(curl -s -X POST http://localhost:5000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Alice","email":"alice@example.com","password":"secret123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Find a path — no auth needed
curl http://localhost:5000/distance/0/1000

# 3. Add a friend — needs token
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/friends/107

# 4. Get personalized suggestions — needs token
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/suggestions/me
```

### Swagger UI

Open `http://localhost:5000/docs`, click **Authorize**, and paste your token. All protected endpoints will unlock.

---

## Graph Visualization

A browser-based demo is served at **`http://localhost:5000`** (redirects to `/static/index.html`).

**Features:**
- Login / register form (JWT stored in `sessionStorage`)
- **Path Finder tab** — enter two user IDs, see the shortest path rendered as an interactive network graph (vis.js). Run the same query twice to see the badge switch from `LIVE (Neo4j)` to `CACHED (Redis)`.
- **Suggestions tab** — enter a user ID, see ranked friend-of-friend suggestions with mutual-friend counts.

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Git

### 1. Clone

```bash
git clone https://github.com/vivek-pippalla/social-network-pathfinding.git
cd social-network-pathfinding
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set a strong `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Start all services

```bash
docker compose up --build
```

Wait ~30 seconds for Neo4j to initialise. The API container starts only after both Neo4j and Redis pass their health checks.

### 4. Seed the database

```bash
docker exec -it social-network-api python scripts/seed_data.py
```

This downloads the Stanford SNAP Facebook dataset and batch-imports **4,039 users** and **88,234 connections** into Neo4j.

### 5. Explore

| URL | What it is |
|---|---|
| `http://localhost:5000` | Graph visualization demo |
| `http://localhost:5000/docs` | Swagger UI (interactive API docs) |
| `http://localhost:7474` | Neo4j Browser (`neo4j` / value from your `.env`) |

---

## Running Tests

```bash
# No Docker needed — tests mock all DB calls
pip install -r requirements.txt
pytest tests/ -v
```

The suite covers:
- Health check
- Auth (register, login, duplicate email, wrong password)
- JWT guard (all protected endpoints return 401 without a token)
- Pathfinding (cache hit, cache miss + Neo4j call, path not found)
- Friend suggestions
- Connection management

---

## Performance

| Scenario | Response Time |
|---|---|
| Cache Miss (Neo4j bidirectional BFS) | ~50–200 ms |
| Cache Hit (Redis) | < 10 ms |
| Friend Suggestions | ~80–150 ms |

Cache keys are **order-independent** — `path:A:B` and `path:B:A` share the same Redis entry, doubling effective hit rate.

---

## Project Structure

```
social-network-pathfinding/
│
├── app/
│   ├── main.py                   # FastAPI entry point, lifespan, CORS, routers, static mount
│   ├── api/
│   │   ├── routes_auth.py        # POST /auth/register, POST /auth/token
│   │   ├── routes_graph.py       # GET /distance, GET /suggestions/me, GET /suggestions/{id}
│   │   ├── routes_users.py       # GET+PUT /profile/me, GET /profile/{id}, GET /profile/search
│   │   └── routes_friends.py     # POST /friends/{id}, DELETE /friends/{id}
│   ├── core/
│   │   ├── auth.py               # JWT encode/decode, bcrypt, get_current_user dependency
│   │   ├── config.py             # Settings via pydantic-settings (.env)
│   │   ├── exceptions.py         # Custom HTTP exceptions (404, 409)
│   │   └── logging_config.py     # Structured JSON logging
│   ├── db/
│   │   ├── neo4j_db.py           # Neo4j driver singleton
│   │   └── redis_cache.py        # Redis client + get/set helpers (fail-safe)
│   ├── models/
│   │   └── schemas.py            # Pydantic request/response models
│   ├── repositories/
│   │   ├── user_repo.py          # User Cypher queries (CRUD + update_user)
│   │   └── graph_repo.py         # Connection + pathfinding Cypher queries
│   ├── services/
│   │   ├── user_service.py       # User business logic
│   │   └── pathfinder.py         # Cache-aside pathfinding + suggestions
│   └── static/
│       └── index.html            # Graph visualization demo (vis.js)
│
├── .github/
│   └── workflows/
│       └── ci.yml                # GitHub Actions: pytest on push/PR
│
├── scripts/
│   └── seed_data.py              # Stanford SNAP dataset importer
├── tests/
│   └── test_api.py               # pytest suite
├── documentation/
│   ├── PRD.md                    # Product requirements
│   ├── TRD.md                    # Technical requirements + full API spec
│   ├── app_flow.md               # Sequence diagrams for every user flow
│   ├── backend_schema.md         # Neo4j, Pydantic, JWT, Redis schemas + all Cypher queries
│   ├── architecture_deep_dive.md # HLD → LLD with code examples
│   ├── project_journal.md        # Full guide + interview prep
│   └── interview_guide.md        # Complete interview walkthrough (pitches, Q&A, demo script)
├── nginx/
│   └── nginx.conf                # Reverse proxy config (optional, not in default compose)
├── .env.example                  # Template — copy to .env and fill in values
├── docker-compose.yml
├── Dockerfile                    # Multi-stage production image
└── requirements.txt
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `password123` | Neo4j password |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `CACHE_TTL_SECONDS` | `3600` | Path cache expiry (1 hour) |
| `SECRET_KEY` | *(must set)* | JWT signing secret — generate with `secrets.token_hex(32)` |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token lifetime (24 hours) |

> **Security note:** Never commit your real `.env` file. It is listed in `.gitignore`.

---

## Dataset

**Stanford SNAP — Facebook Social Circles** (`ego-Facebook`)

| Property | Value |
|---|---|
| Nodes | 4,039 users |
| Edges | 88,234 connections |
| Avg degree | ~21.9 connections/user |
| Avg path length | ~3.7 hops |
| Distribution | Scale-free (power-law) |
| Source | https://snap.stanford.edu/data/ego-Facebook.html |

---

## License

MIT License — see [LICENSE](LICENSE) for details.
