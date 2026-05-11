# Project Guide: Everything From Scratch to End
## Understanding Every Mechanism and Design Decision

---

## Chapter 1: The Problem We Are Solving

### The Core Question
Given a social network of users connected by friendships, how do you efficiently answer:
*"What is the shortest chain of connections between User A and User B?"*

This is the **"Six Degrees of Separation"** problem. Research shows that any two people on Earth are connected through at most 6 social hops. LinkedIn calls this "1st, 2nd, 3rd connections."

### Why Is This Hard?
- A social network is a **graph** — not a table, not a list.
- Brute force search is impossible at scale: Facebook has 3 billion users. Checking every possible path would take years.
- The data is highly **interconnected** — SQL databases are terrible at this because they require expensive JOIN operations for every hop.

### Our Solution
Use the right tool for the job:
- **Neo4j** (native graph DB) for storing and traversing relationships
- **Redis** for caching expensive query results
- **FastAPI** for a clean, fast REST API layer

---

## Chapter 2: How Graphs Work (The Core CS Concept)

### What Is a Graph?
A **graph** is a data structure with:
- **Nodes** (also called vertices): The entities. In our case: Users.
- **Edges** (also called relationships): The connections. In our case: Friendships.

```
    [User_0] ── [User_107] ── [User_150]
                    │
                [User_348]
```

### Directed vs Undirected
- **Directed:** Edges have a direction (Twitter follow — A follows B but B doesn't follow A)
- **Undirected:** No direction (Facebook friendship — if A is friends with B, B is friends with A)

Our project uses **undirected** relationships: `(a)-[:CONNECTED]-(b)` (note the `-` on both sides, not `->`).

### Why Neo4j Over SQL for Graphs?

In **SQL**, to find friends-of-friends:
```sql
SELECT f2.user_id
FROM friendships f1
JOIN friendships f2 ON f1.friend_id = f2.user_id
WHERE f1.user_id = 'A'
```
For 6 hops, you need 6 JOINs. Each JOIN scans the entire friendship table. With 88,234 edges, this gets exponentially slow.

In **Neo4j**, relationships are stored as **physical pointers** on each node. Traversal is just following a pointer — O(1) per hop regardless of how large the database is.

---

## Chapter 3: How Shortest Path Works

### Breadth-First Search (BFS)
BFS is the algorithm for finding shortest paths in an unweighted graph. It works like ripples spreading from a stone dropped in water — it explores all nodes 1 hop away, then all nodes 2 hops away, then 3 hops, etc.

```
Start at User_0:

Level 0 (visited): {0}
Level 1 (1 hop away): {107, 42, 88}
Level 2 (2 hops away): {150, 205, 319, ...}
                              ↑
                         Found User_150!
                         Path: 0 → 107 → 150
```

**BFS guarantees the SHORTEST path** because it always explores closer nodes before farther ones.

### Bidirectional BFS (What Neo4j Does Internally)
Instead of running BFS from just one end, Neo4j runs **two BFS searches simultaneously** — one from the start node expanding forward, one from the end node expanding backward. They meet in the middle.

```
Forward BFS from User_0:    {107, 42, 88}
Backward BFS from User_150: {107, 201, 88}

They both reached User_107!
Path: 0 → 107 → 150
```

**Why faster?** If the graph has branching factor `b` and the path length is `d`:
- One-way BFS explores: `b^d` nodes
- Bidirectional BFS explores: `2 × b^(d/2)` nodes

For d=6, b=10: One-way = 1,000,000 nodes. Bidirectional = 2×1,000 = 2,000 nodes. **500x faster.**

---

## Chapter 4: The FastAPI Application — Layer by Layer

### How a Request Travels Through the Code

Let's trace a real request: `GET /api/v1/path/0/150`

#### Step 1 — Uvicorn receives the HTTP request
`uvicorn` is the ASGI server that runs our FastAPI app. When a request arrives, uvicorn passes it to FastAPI's routing engine.

#### Step 2 — FastAPI router matches the URL
```python
# routes_graph.py
@router.get("/path/{start_user}/{end_user}")
def get_shortest_path(start_user: str, end_user: str, driver: Driver = Depends(get_driver)):
```
FastAPI sees `/api/v1/path/0/150` and matches it to this function. It extracts `start_user="0"` and `end_user="150"` from the URL.

`Depends(get_driver)` tells FastAPI: *"Before calling this function, run `get_driver()` and inject the result as `driver`."*

#### Step 3 — FastAPI injects the Neo4j driver
```python
# neo4j_db.py
def get_driver() -> Driver:
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(...)  # Only happens once
    return _driver  # Returns the cached singleton
```

#### Step 4 — Route calls the Service
```python
return pathfinder.find_shortest_path(driver, start_user, end_user)
```

#### Step 5 — Service checks Redis first
```python
# pathfinder.py
cache_key = f"path:{min('0','150')}:{max('0','150')}"  # = "path:0:150"
cached_result = redis_cache.get_cached_path(cache_key)

if cached_result:                    # Cache HIT
    cached_result["cached"] = True
    return cached_result             # Returns immediately, ~1ms
```

#### Step 6 — On cache miss, calls the Repository
```python
# pathfinder.py
path = graph_repo.find_shortest_path(driver, start_id, end_id)
```

#### Step 7 — Repository executes Cypher query
```python
# graph_repo.py
result = session.run("""
    MATCH (a:User {id: $start}), (b:User {id: $end})
    MATCH path = shortestPath((a)-[:CONNECTED*]-(b))
    RETURN [node IN nodes(path) | node.id] AS path
""", start=start_id, end=end_id)
```

Neo4j runs its internal bidirectional BFS and returns the path.

#### Step 8 — Service caches the result
```python
redis_cache.set_cached_path(cache_key, result)
# Internally runs: SETEX "path:0:150" 3600 '{"path": ["0","107","150"]...}'
```

#### Step 9 — FastAPI serializes and returns the response
Pydantic validates that the return value matches the `PathResponse` schema and FastAPI sends it as JSON.

---

## Chapter 5: Redis Caching — Explained Simply

### What Is Redis?
Redis is an **in-memory database**. All data lives in RAM, not on disk. This makes it extremely fast — reading a key takes ~0.1ms compared to ~150ms for a Neo4j query.

### The GET → SET Pattern
Our cache has only two operations:

**On read request:**
```python
data = redis_client.get("path:0:150")
# Returns: '{"path": ["0","107","150"], "hops": 2}' (string)
# Or: None (if key doesn't exist or has expired)
```

**On cache miss (after Neo4j query):**
```python
redis_client.setex("path:0:150", 3600, json.dumps(result))
# SETEX = SET with EXpiry
# 3600 = TTL in seconds (1 hour)
```

### What Is TTL (Time-To-Live)?
TTL is an expiration timer on a Redis key. After `3600` seconds, Redis automatically deletes the key. The next request for the same path will go to Neo4j again.

**Why TTL matters:** If two users become friends, the shortest path between other users might change (the new friendship creates a shortcut). TTL ensures stale cached paths eventually expire and get refreshed.

---

## Chapter 6: Pydantic — Data Validation

### What Is Pydantic?
Pydantic automatically validates incoming HTTP request data against a Python class definition. If the data doesn't match, it returns a clear 422 error — no code needed from you.

```python
class UserCreate(BaseModel):
    name: str           # Required. Must be a string.
    email: Optional[str] = None  # Optional. Defaults to None.
```

When a client sends:
```json
{"name": 123}   ← number instead of string
```
Pydantic automatically coerces `123` → `"123"` (it's smart about this). But:
```json
{}   ← missing required field
```
Returns a 422 Unprocessable Entity error automatically.

### Why This Matters
Without Pydantic, you'd write manual validation for every field of every endpoint. With Pydantic, your schemas ARE your validation.

---

## Chapter 7: Docker and Docker Compose

### Why Docker?
Without Docker, someone cloning your repo must manually install Python 3.11, Neo4j, Redis, set up all environment variables, and pray it works on their machine.

With Docker, they run `docker compose up` and the entire system starts identically on any machine.

### How docker-compose.yml Works
```yaml
services:
  api:                      # Service name: "api"
    build: .                # Build from Dockerfile in current directory
    ports:
      - "5000:5000"         # Map host port 5000 → container port 5000
    env_file: .env          # Load environment variables from .env file
    depends_on:
      neo4j:
        condition: service_healthy   # Don't start until neo4j passes healthcheck
```

### What Is a Healthcheck?
```yaml
healthcheck:
  test: ["CMD", "redis-cli", "ping"]   # Run this command inside the container
  interval: 10s                         # Every 10 seconds
  retries: 5                            # Must pass 5 times to be "healthy"
```

Without healthchecks, the `api` container might start before Neo4j is ready, fail to connect, and crash. Healthchecks ensure proper startup ordering.

### What Are Named Volumes?
```yaml
volumes:
  neo4j_data:/data    # Store Neo4j's database files in a named Docker volume
```

Named volumes persist data on your host machine's disk even when containers stop. This is why your seeded data survives a `docker compose down`.

### Multi-Stage Dockerfile
```dockerfile
FROM python:3.11-slim AS builder    # Stage 1: install dependencies
RUN pip install -r requirements.txt

FROM python:3.11-slim               # Stage 2: copy only what we need
COPY --from=builder /usr/local /usr/local  # Copy installed packages from Stage 1
```

**Why two stages?** The builder stage installs `gcc`, `make`, etc. (needed to compile some Python packages). We don't need those tools in production — they just add unnecessary image size. The final image only contains the app and its installed packages.

---

## Chapter 8: Structured JSON Logging

### Why Logging?
In production, you can't attach a debugger. Logs are your only window into what your application is doing. When something breaks at 3am, structured logs help you find the issue in seconds.

### Why JSON Logs?
```
# Unstructured (bad):
2026-05-06 17:30:00 INFO: Cache MISS | key=path:0:150

# Structured JSON (good):
{"level": "INFO", "message": "Cache MISS | key=path:0:150", "module": "redis_cache"}
```
JSON logs can be ingested by any log collector (ELK Stack, Loki, AWS CloudWatch) and searched/filtered programmatically.

---

## Chapter 9: API Design Principles

### REST Conventions Used

| Convention | Example | Reason |
|---|---|---|
| Plural nouns for resources | `/users`, `/connections` | REST standard |
| HTTP verbs for actions | `POST` = create, `GET` = read | Semantic clarity |
| Status codes | `201` = created, `404` = not found | Standard HTTP semantics |
| Versioned URLs | `/api/v1/...` | Allows future `/api/v2/` without breaking clients |

### Swagger/OpenAPI
FastAPI automatically generates interactive documentation at `/docs`. Every endpoint, request schema, and response schema is documented without writing a single line of documentation code. Pydantic schemas become the API documentation.

---

## Chapter 10: The Seed Data Script

### Why Not Just Use Random Data?
Random connections don't reflect real-world social networks. In a real network:
- A few "hub" nodes (celebrities/influencers) have thousands of connections
- Most nodes have just a few connections
- This creates a **power-law distribution** (few nodes with very high degree)

The Stanford SNAP Facebook dataset has this real-world distribution — making our demo much more realistic and credible.

### How the Batch Insertion Works
```python
for i in range(0, len(user_ids), BATCH_SIZE):
    batch = user_ids[i : i + BATCH_SIZE]
    session.execute_write(_batch_create_users, batch)
```

Instead of 4,039 separate `CREATE` queries (slow), we group them into batches of 500. Neo4j processes each batch as a single transaction, dramatically reducing network round-trips.

**Why BATCH_SIZE = 500?**
Too small = too many round-trips. Too large = single transaction holds locks for too long. 500 is a common sweet spot for Neo4j bulk operations.
