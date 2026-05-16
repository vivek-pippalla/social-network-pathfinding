# Architecture Deep Dive: Social Network Pathfinding Engine
## From High-Level Design (HLD) to Low-Level Design (LLD)

---

## Part 1: High-Level Design (HLD)

### 1.1 What Problem Does This System Solve?

Imagine LinkedIn asking: *"How is Vivek connected to Satya Nadella?"*
The answer requires traversing a graph of potentially millions of users and friendships to find the shortest chain of connections.

This system solves exactly that — finding the **shortest path** between any two users in a social network, efficiently.

---

### 1.2 System Context Diagram

```
┌─────────────────────────────────────────────────────┐
│                   EXTERNAL CLIENTS                  │
│   Postman / Swagger UI / Frontend App / curl        │
└───────────────────┬─────────────────────────────────┘
                    │ HTTP Requests
                    ▼
┌─────────────────────────────────────────────────────┐
│              DOCKER NETWORK (Isolated)              │
│                                                     │
│  ┌─────────────┐   ┌──────────┐   ┌─────────────┐  │
│  │   FastAPI   │──▶│  Redis   │   │   Neo4j     │  │
│  │   Port 5000 │   │ Port 6379│   │  Port 7687  │  │
│  │             │──▶│          │   │  Port 7474  │  │
│  │  (Our App)  │   │  Cache   │   │  (Graph DB) │  │
│  └─────────────┘   └──────────┘   └─────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

### 1.3 Why Each Technology Was Chosen

| Technology | Why We Chose It |
|---|---|
| **FastAPI** | Async-ready, auto-generates Swagger docs, uses Python type hints for auto-validation via Pydantic. Fastest Python web framework. |
| **Neo4j** | A *native graph database*. Relationships are first-class citizens — it stores them as physical pointers, not as join tables like SQL. This makes graph traversal 10–100x faster than SQL for connected data. |
| **Redis** | An in-memory key-value store. Since pathfinding queries are expensive (Neo4j traversal), we cache results. Redis reads take ~0.1ms vs ~150ms for Neo4j. |
| **Docker Compose** | Packages all 3 services into a single, reproducible environment. One command (`docker compose up`) starts everything. |

---

### 1.4 High-Level Request Flow

```
Client
  │
  │  GET /api/v1/path/0/150
  ▼
FastAPI Application
  │
  ├─── Check Redis Cache (key: "path:0:150")
  │         │
  │    ┌────┴──────┐
  │    │           │
  │  HIT         MISS
  │    │           │
  │    │     Query Neo4j
  │    │       shortestPath()
  │    │           │
  │    │     Save result
  │    │     to Redis (1hr TTL)
  │    │           │
  └────┴───────────┘
            │
            ▼
     Return JSON Response
     {path: [0, 107, 150], hops: 2, cached: true/false}
```

---

### 1.5 Data Model in Neo4j

Neo4j stores data as **nodes** (entities) and **relationships** (edges).

```
(User {id: "0", name: "User_0"})
          │
     [:CONNECTED]          ← This is the RELATIONSHIP (edge)
          │
(User {id: "107", name: "User_107"})
          │
     [:CONNECTED]
          │
(User {id: "150", name: "User_150"})
```

**Key insight:** In SQL, finding this path would require expensive JOIN operations across a friendship table. In Neo4j, each node physically stores a pointer to its relationships, so traversal is **O(depth)** not **O(total_rows)**.

---

### 1.6 Dataset: Stanford SNAP Facebook Graph

| Property | Value |
|---|---|
| **Source** | Stanford Network Analysis Project (SNAP) |
| **Dataset** | Facebook Social Circles (ego-Facebook) |
| **Nodes** | 4,039 users |
| **Edges** | 88,234 connections |
| **Avg. connections per user** | ~21.9 |
| **Network type** | Scale-free (power-law distribution — a few very popular nodes, most with few connections) |

This means some users (the "hubs") are connected to hundreds of others — just like real social networks where celebrities have millions of followers.

---

## Part 2: Low-Level Design (LLD)

### 2.1 The 4-Tier Architecture

```
HTTP Request
     │
     ▼
┌──────────────────────────────────┐
│  TIER 1: API / Router Layer      │  app/api/routes_*.py
│  - Accepts HTTP request          │
│  - Validates input via Pydantic  │
│  - Calls the Service layer       │
└──────────────────┬───────────────┘
                   │
                   ▼
┌──────────────────────────────────┐
│  TIER 2: Service Layer           │  app/services/*.py
│  - Contains business logic       │
│  - Decides WHAT to do            │
│  - Coordinates cache + database  │
└──────────────────┬───────────────┘
                   │
                   ▼
┌──────────────────────────────────┐
│  TIER 3: Repository Layer        │  app/repositories/*.py
│  - Knows HOW to talk to the DB   │
│  - Executes raw Cypher queries   │
│  - Returns plain Python objects  │
└──────────────────┬───────────────┘
                   │
                   ▼
┌──────────────────────────────────┐
│  TIER 4: Database/Driver Layer   │  app/db/*.py
│  - Manages Neo4j driver instance │
│  - Manages Redis client instance │
│  - Connection pooling            │
└──────────────────────────────────┘
```

**Why separate these tiers?**
Each tier has ONE responsibility. If you need to swap Neo4j for a different database tomorrow, you only change the **Repository layer** — the Service layer and API layer are completely untouched. This is the **Single Responsibility Principle**.

---

### 2.2 Design Patterns Used (Explain These in Interviews)

#### Pattern 1: Singleton Pattern (app/db/neo4j_db.py)

```python
_driver: Driver = None          # Module-level variable (shared across all requests)

def get_driver() -> Driver:
    global _driver
    if _driver is None:         # Only create ONE driver ever
        _driver = GraphDatabase.driver(...)
    return _driver              # Always return the SAME instance
```

**Why:** Neo4j drivers manage an internal connection pool (like having 10 persistent connections ready). Creating a new driver per request would be wasteful and slow. The Singleton ensures we reuse the same pool.

---

#### Pattern 2: Dependency Injection (app/api/routes_*.py)

```python
@router.get("/path/{start}/{end}")
def get_shortest_path(
    start: str,
    end: str,
    driver: Driver = Depends(get_driver)  # FastAPI INJECTS the driver
):
```

**Why:** The route function doesn't create the driver itself — FastAPI calls `get_driver()` and passes the result in. This makes the function easy to test (you can inject a fake driver in tests).

---

#### Pattern 3: Repository Pattern (app/repositories/)

All raw database queries are isolated in repository files. The service never writes Cypher directly.

```python
#  Correct — service calls repository
def find_shortest_path(driver, start_id, end_id):
    path = graph_repo.find_shortest_path(driver, start_id, end_id)  # Repository handles DB

#  Wrong — service writing Cypher directly (breaks separation of concerns)
def find_shortest_path(driver, start_id, end_id):
    result = driver.session().run("MATCH path = shortestPath(...)...")
```

---

#### Pattern 4: Lifespan Context Manager (app/main.py)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    get_driver()    # ← Runs on STARTUP (warms up Neo4j connection)
    yield           # ← Application runs here
    close_driver()  # ← Runs on SHUTDOWN (closes connections gracefully)
```

**Why:** Without this, the first request would be slow (connection setup). With this, the connection is ready before any request arrives.

---

### 2.3 Caching Layer Deep Dive

#### How the Cache Key Works

```python
cache_key = f"path:{min(start_id, end_id)}:{max(start_id, end_id)}"
```

`min()` and `max()` make the key **order-independent**:
- Path from `0 → 150` → key: `path:0:150`
- Path from `150 → 0` → key: `path:0:150` ← SAME KEY

This means both directions hit the same cache entry, doubling cache efficiency.

---

#### Redis Data Structure for Cache

```
Redis Key:          "path:0:150"
Redis Value:        '{"start_user": "0", "end_user": "150", "path": ["0","107","150"], "hops": 2}'
Expiry (TTL):       3600 seconds (1 hour)
Redis Command:      SETEX "path:0:150" 3600 "{...json...}"
```

After 1 hour, Redis automatically deletes the key. The next request will re-query Neo4j and re-cache the result.

---

### 2.4 Neo4j Query Deep Dive

#### The shortestPath Query

```cypher
MATCH (a:User {id: $start}), (b:User {id: $end})
MATCH path = shortestPath((a)-[:CONNECTED*]-(b))
RETURN [node IN nodes(path) | node.id] AS path
```

**Breaking this down line by line:**
1. `MATCH (a:User {id: $start})` — Find the start user node
2. `MATCH (b:User {id: $end})` — Find the end user node
3. `shortestPath((a)-[:CONNECTED*]-(b))` — Find the shortest path traversing any number (`*`) of `CONNECTED` relationships between them
4. `[node IN nodes(path) | node.id]` — Extract just the `id` from each node in the path (list comprehension in Cypher)

**What Neo4j does internally:** It runs a **Bidirectional BFS** — one BFS from `a` expanding outward, one from `b` expanding inward. They meet in the middle. This is far faster than single-direction BFS for deep graphs.

---

#### The Friend Suggestion Query

```cypher
MATCH (u:User {id: $id})-[:CONNECTED]-(friend)-[:CONNECTED]-(fof:User)
WHERE fof.id <> $id
  AND NOT (u)-[:CONNECTED]-(fof)
RETURN fof.id AS suggested_user, count(friend) AS mutual_count
ORDER BY mutual_count DESC
LIMIT 10
```

**Logic:**
- Start at user `u`
- Hop 1: Find all of `u`'s direct friends
- Hop 2: Find all of those friends' friends (`fof` = friend-of-friend)
- Filter: Remove `u` itself and anyone already connected to `u`
- Count: How many mutual friends does `u` share with each `fof`?
- Sort by mutual count → higher mutual count = better suggestion

This is exactly how LinkedIn's "People You May Know" works at a basic level.

---

### 2.5 File-by-File Responsibility Map

```
app/
├── main.py                  → App startup, CORS, router registration, lifespan
├── api/
│   ├── routes_users.py      → HTTP endpoints for user creation/retrieval
│   └── routes_graph.py      → HTTP endpoints for connections, path, suggestions
├── core/
│   ├── config.py            → Reads .env variables, provides settings object
│   ├── exceptions.py        → Custom 404/409 HTTP exceptions
│   └── logging_config.py    → JSON log formatter, setup_logging()
├── db/
│   ├── neo4j_db.py          → Singleton Neo4j driver, get_driver(), close_driver()
│   └── redis_cache.py       → get_cached_path(), set_cached_path()
├── models/
│   └── schemas.py           → Pydantic models for request/response validation
├── repositories/
│   ├── user_repo.py         → Cypher: CREATE User, MATCH User
│   └── graph_repo.py        → Cypher: MERGE connection, shortestPath, suggestions
└── services/
    ├── user_service.py      → Business logic: create user, get user, search
    └── pathfinder.py        → Cache check → Neo4j query → Cache store
```

---

### 2.6 Docker Architecture

```yaml
# Each service is an isolated container
# They communicate via the internal "social-network" bridge network

api:        → Runs uvicorn serving FastAPI
neo4j:      → Runs Neo4j database process
redis:      → Runs Redis in-memory store

# Health checks ensure startup ORDER is respected:
# Redis must be healthy → Neo4j must be healthy → THEN api starts
```

**Named Volumes** (`neo4j_data`, `redis_data`) persist data between container restarts. Your 4,039 users survive a `docker compose down` and `docker compose up`.
