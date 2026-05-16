# Social Network Pathfinding Engine

A Backend service that computes the **shortest connection path** between users in a social graph — similar to LinkedIn's "degrees of connection" feature.

Built with **FastAPI**, **Neo4j**, and **Redis**, seeded with the real-world [Stanford SNAP Facebook dataset](https://snap.stanford.edu/data/ego-Facebook.html) (4,039 users · 88,234 connections).

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [API Endpoints](#api-endpoints)
- [Getting Started](#getting-started)
- [Running Tests](#running-tests)
- [Performance](#performance)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)

---

## Overview

This project answers the question: *"How are two people connected in a social network?"*

Given two user IDs, the engine finds the shortest path through the social graph using Neo4j's built-in graph traversal capabilities. Results are cached in Redis so repeated queries return in under 10ms.

The system also provides a **"People You May Know"** endpoint — ranking friend-of-friend suggestions by mutual friend count using the Triadic Closure algorithm.

---

## Features

- **Shortest Path** — finds the minimum hops between any two users in the graph
- **Redis Caching** — cache-aside pattern with order-independent keys; reduces latency from ~120ms → sub-10ms on cache hits
- **Friend Suggestions** — friends-of-friends ranked by mutual connection count (Triadic Closure)
- **User Management** — create users, fetch by ID, search by name
- **Layered Architecture** — strict Router → Service → Repository → DB separation
- **Containerized** — full Docker Compose setup with health checks for all services
- **Observability** — Prometheus metrics + Grafana dashboards for latency and cache monitoring
- **Structured Logging** — JSON-formatted logs across all layers
- **Custom Exceptions** — typed HTTP exceptions (404, 409) with descriptive messages
- **Automated Tests** — pytest suite with mocked dependencies

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI + Pydantic v2 |
| Graph Database | Neo4j 5.12 |
| Caching | Redis 7 |
| Containerization | Docker + Docker Compose |
| Monitoring | Prometheus + Grafana |
| Testing | pytest + httpx |
| Language | Python 3.11 |


## Why Neo4j Instead of SQL?

Graph databases are optimized for relationship traversal problems.
Traditional relational databases require expensive JOIN operations for multi-hop relationships, while Neo4j efficiently traverses connected nodes using graph-native storage and indexing.

---

## Architecture

### High-Level Design

```
Client (Postman / Swagger / Frontend)
            │
            ▼ HTTP/REST
    ┌───────────────────┐
    │   FastAPI Server  │
    └───────┬───────────┘
            │
     ┌──────┴──────┐
     ▼             ▼
 Redis Cache    Neo4j Graph DB
 (Cache-Aside)  (Source of Truth)
```

### Request Flow — Pathfinding

```
GET /api/v1/path/{start}/{end}
        │
        ▼
  routes_graph.py  (Router Layer)
        │
        ▼
  pathfinder.py    (Service Layer)
        │
        ├── redis_cache.get()
        │        │
        │   ┌────┴────┐
        │   │ HIT     │ MISS
        │   ▼         ▼
        │ Return    graph_repo.find_shortest_path()
        │ cached        │
        │ result    Neo4j shortestPath() — bidirectional BFS
        │                │
        │           redis_cache.set()  ← TTL: 1 hour
        │                │
        └────────────────┘
                 │
                 ▼
          PathResponse JSON
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

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/users` | Create a new user |
| `GET` | `/api/v1/users/{id}` | Get user by ID |
| `GET` | `/api/v1/users/search?q=` | Search users by name |
| `POST` | `/api/v1/connections` | Create a connection between two users |
| `GET` | `/api/v1/path/{start}/{end}` | Find shortest path between two users |
| `GET` | `/api/v1/suggestions/{user_id}` | Get friend suggestions (top 10) |

Full interactive docs available at **`http://localhost:5000/docs`** (Swagger UI) after running the project.

### Example — Shortest Path

**Request:**
```
GET /api/v1/path/0/150
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

### Example — Friend Suggestions

**Request:**
```
GET /api/v1/suggestions/0
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

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Git

### 1. Clone the repository

```bash
git clone https://github.com/vivek-pippalla/social-network-pathfinding.git
cd social-network-pathfinding
```

### 2. Configure environment variables

Create a `.env` file in the root directory:

```env
# Neo4j
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123

# Redis
REDIS_URL=redis://redis:6379/0

# Cache TTL (seconds)
CACHE_TTL_SECONDS=3600
```

> **Note:** Use `bolt://neo4j:7687` when running inside Docker. Use `bolt://localhost:7687` for local development without Docker.

### 3. Start all services

```bash
docker-compose up --build
```

This starts three containers:
- `social-network-api` — FastAPI app on port `5000`
- `social-network-neo4j` — Neo4j on ports `7474` (browser) and `7687` (bolt)
- `social-network-redis` — Redis on port `6379`

Wait for all health checks to pass (~30 seconds for Neo4j to initialize).

### 4. Seed the database

In a new terminal, run:

```bash
docker exec -it social-network-api python scripts/seed_data.py
```

This downloads the Stanford SNAP Facebook dataset and batch-imports **4,039 users** and **88,234 connections** into Neo4j.

### 5. Explore the API

- **Swagger UI:** http://localhost:5000/docs
- **Neo4j Browser:** http://localhost:7474 (login: `neo4j` / `password123`)
- **Grafana Dashboard:** http://localhost:3000

---

## Running Tests

```bash
# Install dependencies locally (if not using Docker)
pip install -r requirements.txt

# Run the test suite
pytest tests/ -v
```

Tests use FastAPI's `TestClient` with mocked Neo4j and Redis dependencies — no live database required.

---

## Performance

| Scenario | Response Time |
|---|---|
| Cache Miss (Neo4j query) | ~50–200ms |
| Cache Hit (Redis) | < 10ms |
| Friend Suggestions | ~80–150ms |

Cache keys are **order-independent** — a query for `path:A:B` and `path:B:A` share the same cache entry, doubling effective cache hit rate.

---

## Project Structure

```
social-network-pathfinding/
│
├── app/
│   ├── main.py                   # FastAPI entry point, lifespan, CORS
│   ├── api/
│   │   ├── routes_users.py       # User endpoints
│   │   └── routes_graph.py       # Connection, path, suggestion endpoints
│   ├── core/
│   │   ├── config.py             # Settings via pydantic-settings
│   │   ├── exceptions.py         # Custom HTTP exceptions
│   │   └── logging_config.py     # Structured logging setup
│   ├── db/
│   │   ├── neo4j_db.py           # Neo4j driver singleton
│   │   └── redis_cache.py        # Redis client + get/set helpers
│   ├── models/
│   │   └── schemas.py            # Pydantic request/response models
│   ├── repositories/
│   │   ├── user_repo.py          # User Cypher queries
│   │   └── graph_repo.py         # Connection + pathfinding Cypher queries
│   └── services/
│       ├── user_service.py       # User business logic
│       └── pathfinder.py         # Cache-aside pathfinding orchestration
│
├── scripts/
│   └── seed_data.py              # Stanford SNAP dataset importer
├── tests/
│   └── test_api.py               # pytest test suite
├── monitoring/
│   ├── prometheus.yml            # Prometheus config
│   └── grafana/                  # Grafana dashboards + datasources
├── nginx/
│   └── nginx.conf                # Reverse proxy config
├── documentation/
│   └── architecture.md           # Detailed HLD + LLD docs
├── docker-compose.yml
├── Dockerfile                    # Multi-stage production image
├── requirements.txt
└── .env.example                  # Template for environment variables
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

---

## Dataset

**Stanford SNAP — Facebook Social Circles** (`ego-Facebook`)

- 4,039 nodes (users)
- 88,234 edges (connections)
- Source: https://snap.stanford.edu/data/ego-Facebook.html

---

## Future Improvements

- JWT Authentication
- Kubernetes deployment
- Distributed cache invalidation
- Async task processing
- Horizontal API scaling
- Load testing with Locust

---
## License
MIT License — see [LICENSE](LICENSE) for details.