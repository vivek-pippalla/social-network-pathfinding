# Interview Preparation Checklist
## Social Network Pathfinding Engine — Complete Study Guide

## SECTION 1: Core Computer Science Concepts

### Graphs
- [ ] What is a graph? (Nodes + Edges)
- [ ] Directed vs Undirected graphs (and which one our project uses, and WHY)
- [ ] Weighted vs Unweighted graphs
- [ ] What is graph degree? (number of connections a node has)
- [ ] What is a path in a graph?
- [ ] What is the shortest path?
- [ ] What does "Six Degrees of Separation" mean?
- [ ] What is a scale-free network / power-law distribution?

**Key answer to practice:**
> *"A graph is a data structure consisting of nodes (users) and edges (friendships). Our project uses an undirected, unweighted graph because friendships are mutual and we don't assign weights to connections."*

---

### Algorithms
- [ ] What is BFS (Breadth-First Search)? How does it work step by step?
- [ ] Why does BFS guarantee the shortest path?
- [ ] What is DFS (Depth-First Search)? When would you use it instead of BFS?
- [ ] What is Bidirectional BFS? Why is it faster?
- [ ] What is the time complexity of BFS? O(V + E) — V=vertices, E=edges
- [ ] What does Neo4j's `shortestPath()` do internally? (Bidirectional BFS)

**Key answer to practice:**
> *"BFS explores the graph level by level — all nodes 1 hop away first, then 2 hops, etc. This guarantees the shortest path because we always find closer nodes before farther ones. Neo4j's shortestPath() runs bidirectional BFS — one search from each end — which is dramatically faster for deep graphs."*

---

### Caching
- [ ] What is caching? Why do we use it?
- [ ] What is a cache hit vs a cache miss?
- [ ] What is TTL (Time-To-Live)?
- [ ] What is cache invalidation? Why is it called "one of the hardest problems in CS"?
- [ ] What is an in-memory database?
- [ ] What is a cache key? How did we design ours to be order-independent?

**Key answer to practice:**
> *"Caching stores the result of expensive computations so future identical requests don't need to redo the work. A cache hit returns instantly (~1ms); a cache miss falls through to the database (~150ms). We use Redis with a 1-hour TTL — after 1 hour, the key expires and the next request refreshes it from Neo4j."*

---

## SECTION 2: Technologies

### FastAPI
- [ ] What is FastAPI? How is it different from Flask?
- [ ] What is ASGI vs WSGI?
- [ ] What is uvicorn and why do we use it?
- [ ] What is automatic documentation? (Swagger UI at /docs, ReDoc at /redoc)
- [ ] What is a router in FastAPI? (APIRouter)
- [ ] What is `Depends()` and Dependency Injection in FastAPI?
- [ ] What is a lifespan context manager? What did we use it for?
- [ ] What are HTTP status codes? (200, 201, 404, 409, 422, 500)
- [ ] What is CORS and why did we enable it?

**Key answer to practice:**
> *"FastAPI is a modern, high-performance Python web framework. Unlike Flask, it's built on ASGI (asynchronous), uses Python type hints for automatic validation, and generates Swagger documentation automatically. We run it with uvicorn, an ASGI server."*

---

### Neo4j
- [ ] What is Neo4j? What makes it a "native" graph database?
- [ ] What is a node in Neo4j?
- [ ] What is a relationship/edge in Neo4j?
- [ ] What are labels in Neo4j? (e.g., `:User`)
- [ ] What are properties in Neo4j? (e.g., `{id: "0", name: "User_0"}`)
- [ ] What is Cypher? (Neo4j's query language)
- [ ] How do you `MATCH` a node in Cypher?
- [ ] How do you `CREATE` a node in Cypher?
- [ ] How do you `MERGE` in Cypher? (CREATE if not exists)
- [ ] How does `shortestPath()` work in Cypher?
- [ ] What is `[:CONNECTED*]` in Cypher? (Variable-length relationship matching)
- [ ] What is the Bolt protocol? (Port 7687)
- [ ] What is the Neo4j Browser? (Port 7474)
- [ ] Why is Neo4j faster than SQL for graph traversal?
- [ ] What is a connection pool in Neo4j?

**Key answer to practice:**
> *"Neo4j stores relationships as physical pointers on each node. When you traverse a relationship, it's just following a pointer in memory — O(1) per hop. In SQL, each hop requires a JOIN operation that scans the entire friendship table, making it exponentially slower as the path gets deeper."*

---

### Redis
- [ ] What is Redis?
- [ ] Why is Redis so fast? (in-memory)
- [ ] What is `GET` in Redis?
- [ ] What is `SET` in Redis?
- [ ] What is `SETEX` in Redis? (SET with Expiry)
- [ ] What is `TTL` in Redis?
- [ ] What does `decode_responses=True` mean in the Python Redis client?
- [ ] What happens when a Redis key expires?
- [ ] What is `json.dumps()` and `json.loads()` and why did we use them?

**Key answer to practice:**
> *"Redis is an in-memory key-value store. We use it to cache pathfinding results. We serialize our path dictionary to a JSON string using json.dumps() before storing it (Redis only stores strings/bytes), and deserialize with json.loads() when reading it back."*

---

### Docker & Docker Compose
- [ ] What is Docker? What problem does it solve?
- [ ] What is a Docker image vs a Docker container?
- [ ] What is a Dockerfile?
- [ ] What is a multi-stage build? Why did we use it?
- [ ] What is `docker compose up -d`? (detached mode)
- [ ] What is `docker compose down`?
- [ ] What is `docker compose logs -f api`?
- [ ] What is a Docker volume? Named vs anonymous volumes?
- [ ] What is a Docker network? (bridge driver)
- [ ] What is a healthcheck in Docker Compose?
- [ ] What is `depends_on` with `condition: service_healthy`?
- [ ] What is `EXPOSE` in a Dockerfile?
- [ ] What does `COPY --from=builder` do in a multi-stage build?

**Key answer to practice:**
> *"Docker packages an application with all its dependencies into a container that runs identically everywhere. Docker Compose lets us define and run multiple containers together. We use a multi-stage Dockerfile — the builder stage installs compilation tools to build Python packages, but the final production image only contains the app and its packages, keeping the image small."*

---

### Pydantic
- [ ] What is Pydantic?
- [ ] What is a Pydantic BaseModel?
- [ ] What is data validation?
- [ ] What is `Optional[str]` in Python?
- [ ] What is a 422 error? (Unprocessable Entity — Pydantic validation failed)
- [ ] What is `response_model` in FastAPI?
- [ ] What is `pydantic-settings`? How does it read from `.env`?

---

## SECTION 3: Software Design Concepts

### Design Patterns (MOST LIKELY TO BE ASKED)
- [ ] **Singleton Pattern** — What is it? Where did we use it? (Neo4j driver, Redis client)
- [ ] **Repository Pattern** — What is it? Why separate DB queries into their own layer?
- [ ] **Dependency Injection** — What is it? How does FastAPI's `Depends()` implement it?
- [ ] **Service Layer Pattern** — What is it? What is "business logic"?
- [ ] **Layered Architecture** — What is it? What are the 4 tiers in our project?

**Key answer to practice for Singleton:**
> *"The Singleton pattern ensures only one instance of a class/object exists. We use it for the Neo4j driver because it manages an internal connection pool. Creating a new driver per request would be extremely wasteful — each one would open new connections, consume memory, and slow down the API."*

**Key answer to practice for Repository:**
> *"The Repository pattern isolates all database queries in one layer. The Service layer never writes Cypher directly — it calls the Repository. This means if we ever need to swap Neo4j for a different database, we only change the repository files. The service and API layers are completely unaffected."*

---

### API Design
- [ ] What is REST? What are the constraints?
- [ ] What is an HTTP method? (GET, POST, PUT, DELETE, PATCH)
- [ ] What is a resource in REST? (noun-based URLs)
- [ ] What is API versioning? (`/api/v1/`)
- [ ] What is OpenAPI/Swagger?
- [ ] What is a request body vs query parameter vs path parameter?
- [ ] What is JSON? Why do we use it for API responses?
- [ ] What is serialization vs deserialization?

---

### System Design Concepts
- [ ] What is latency? (time for one request to complete)
- [ ] What is throughput? (requests per second)
- [ ] What is a connection pool?
- [ ] What is a single point of failure?
- [ ] What is separation of concerns?
- [ ] What is the Single Responsibility Principle?
- [ ] What is horizontal vs vertical scaling?
- [ ] What is a microservice? Is our project a microservice?
- [ ] What is a monolith vs microservice?
- [ ] What is the CAP theorem? (Consistency, Availability, Partition Tolerance — choose 2)

---

## SECTION 4: Python Concepts Used in This Project

- [ ] What is a context manager? (`with` statement)
- [ ] What is `@asynccontextmanager`?
- [ ] What is `async` / `await` in Python? (Concurrency vs Parallelism)
- [ ] What is a decorator in Python? (`@router.get(...)`, `@app.get(...)`)
- [ ] What is a type hint in Python? (`def foo(x: str) -> dict:`)
- [ ] What is `global` in Python? (Used in our singleton pattern)
- [ ] What is a Python module vs package? (difference between `file.py` and a folder with `__init__.py`)
- [ ] What is `os.getenv()`?
- [ ] What is `json.dumps()` vs `json.loads()`?
- [ ] What is a list comprehension? (`[x for x in list]`)
- [ ] What is `uuid.uuid4()`?
- [ ] What is `time.perf_counter()`? (High-resolution timer)

---

## SECTION 5: The Dataset

- [ ] What is the Stanford SNAP dataset?
- [ ] What is the `ego-Facebook` dataset specifically?
- [ ] How many nodes and edges does it have? (4,039 users, 88,234 connections)
- [ ] What is a scale-free network?
- [ ] What is preferential attachment? (Popular nodes attract more connections)
- [ ] What is a `.gz` file? How did we open it in Python? (`gzip.open()`)
- [ ] Why did we use batch insertion? What is `BATCH_SIZE = 500`?
- [ ] What is `MERGE` vs `CREATE` in Cypher and why did we use `MERGE` for connections?

---

## SECTION 6: Performance & Optimization Section

- [ ] Why is Redis faster than Neo4j?
- [ ] What is network latency?
- [ ] What is serialization overhead?
- [ ] Why are graph traversals expensive?
- [ ] Why is bidirectional BFS faster than normal BFS?
- [ ] What is connection pooling?
- [ ] Why avoid creating DB connections per request?
- [ ] Why cache shortest paths?
- [ ] What are cache stampedes?
- [ ] What is warm cache vs cold cache?
- [ ] Why are indexes important in databases?
- [ ] Did we index user IDs in Neo4j?
- [ ] What metrics would you monitor in production?
- [ ] What is memory vs CPU tradeoff?

Key answer:

“The biggest optimization in our system is avoiding repeated graph traversal. Pathfinding is computationally expensive, so caching previously computed paths in Redis drastically reduces latency and database load.”

---

## SECTION 7: Production Engineering Concepts

- [ ] What is environment configuration?
- [ ] Why use .env files?
- [ ] Why never hardcode secrets?
- [ ] What is structured logging?
- [ ] What is observability?
- [ ] What are logs vs metrics vs traces?
- [ ] What is health monitoring?
- [ ] What happens if Neo4j crashes?
- [ ] What happens if Redis crashes?
- [ ] What is retry logic?
- [ ] What is graceful degradation?
- [ ] What is idempotency?
- [ ] What is rate limiting?
- [ ] What is API throttling?
- [ ] What is request timeout?
- [ ] What is circuit breaker pattern?
Key answer:

“The system is designed with graceful degradation. If Redis fails, requests still succeed through Neo4j directly. This improves reliability and fault tolerance.”

---

## SECTION 8: Security Concepts

- [ ] What is CORS?
- [ ] Why is exposing databases publicly dangerous?
- [ ] What is API authentication?
- [ ] Difference between authentication and authorization
- [ ] What is JWT?
- [ ] What is HTTPS?
- [ ] Why should secrets never be committed to GitHub?
- [ ] What is environment variable injection?
- [ ] What is input validation?
- [ ] How does Pydantic improve security?
- [ ] What are common API vulnerabilities?
- [ ] What is SQL/NoSQL injection?
Key answer:

“Pydantic automatically validates incoming request data, which prevents malformed or invalid payloads from reaching the application logic.”

---

## SECTION 9: “Tradeoffs” Section

- [ ] Why choose Neo4j over PostgreSQL?
- [ ] Why choose Redis over in-process caching?
- [ ] Why choose FastAPI over Flask?
- [ ] Why Docker Compose instead of Kubernetes?
- [ ] Why use REST instead of GraphQL?
- [ ] Why cache paths instead of recomputing?
- [ ] Why use shortestPath() instead of implementing BFS manually?
- [ ] Why use bidirectional BFS?
- [ ] What are downsides of graph databases?
- [ ] What are downsides of caching?

---

## SECTION 10: “Failure Scenarios” 

- [ ] What happens if Redis is unavailable?
- [ ] What happens if Neo4j is unavailable?
- [ ] What happens if the path doesn’t exist?
- [ ] What happens if invalid IDs are provided?
- [ ] What happens if the dataset grows 1000x?
- [ ] What if memory usage becomes too high?
- [ ] What if cache size grows indefinitely?
- [ ] What if too many users hit the API simultaneously?

Key answer:

“In distributed systems, failure is expected, not exceptional. The system should fail gracefully instead of crashing entirely.”

---

## SECTION 11: “Resume Defense Questions”

- [ ] Why did you choose this project?
- [ ] What was the hardest technical challenge?
- [ ] What bug took the longest to solve?
- [ ] What would you improve next?
- [ ] What feature are you most proud of?
- [ ] What did you learn from this project?
- [ ] What would you redesign if starting over?
- [ ] What part was hardest to understand?
- [ ] What would break first at scale?
- [ ] Did you work alone or in a team?
- [ ] How long did it take?
- [ ] What was your biggest engineering decision?

 ---

 ## SECTION 12: “Scalability Deep Dive”

 - [ ] How would you scale this to 100M users?
 - [ ] Horizontal vs Vertical scaling?
 - [ ] Should Neo4j be clustered?
 - [ ] Sharding strategy?
 - [ ] Redis replication?
 - [ ] Load balancing?
 - [ ] Database connection pooling?
 - [ ] Caching at scale?
 - [ ] Monitoring?
 - [ ] What happens at 1 million users?
 - [ ] What happens at 100 million users?
 - [ ] Can shortestPath become expensive?
 - [ ] How would sharding work in graph databases?
 - [ ] What is stateless architecture?
 - [ ] Why are containers useful for scaling?

## SECTION 13: Expected Interview Questions with Model Answers

### "Walk me through your project."
> *"I built a social network pathfinding engine that finds the shortest connection between any two users. It's built with FastAPI as the web layer, Neo4j as the graph database, and Redis for caching. I used the Stanford SNAP Facebook dataset — 4,039 real users and 88,234 connections. The core feature is a pathfinding endpoint that checks Redis first for a cached result; on a miss, it queries Neo4j using its native shortestPath function which internally runs bidirectional BFS. The result is then cached in Redis with a 1-hour TTL. The whole system is containerised with Docker Compose and you can explore the graph visually through the Neo4j Browser."*

---

### "Why Neo4j instead of MySQL or PostgreSQL?"
> *"SQL databases store relationships in join tables. Finding a 3-hop path between users requires 3 JOIN operations, each scanning the entire friendship table. As the dataset grows, this becomes exponentially slower. Neo4j is a native graph database — it stores relationships as physical pointers on each node. Traversal is just following a pointer, which is O(1) per hop regardless of database size. For any problem where the data is highly interconnected — social networks, fraud detection, recommendation engines — a graph database is significantly more appropriate."*

---

### "What happens if Redis is down?"
> *"I designed the Redis cache helper to catch all exceptions and return None on failure. If Redis is down, `get_cached_path()` returns None, the cache miss path is taken, and Neo4j is queried directly. The API still works — just slower. This is called graceful degradation. Redis errors are logged so we can see them in production."*

---

### "What is the time complexity of your pathfinding?"
> *"Our project delegates the traversal to Neo4j's native shortestPath, which runs bidirectional BFS internally. Theoretically, BFS is O(V + E) where V is the number of vertices and E is the number of edges. In practice for a social network query, only a small subset of the graph is explored before the two frontiers meet."*

---

### "Why Redis TTL of 1 hour?"
> *"TTL is a trade-off between cache freshness and performance. A very short TTL means the cache expires frequently and we hit Neo4j more often — defeating the purpose of caching. A very long TTL means cached paths could become stale if new friendships are added. 1 hour is a reasonable middle ground for a social network where the graph topology doesn't change every second."*

---

### "What is the 4-tier architecture and why?"
> *"The 4 tiers are API Layer, Service Layer, Repository Layer, and Database Layer. Each has one responsibility. The API layer handles HTTP, the Service layer handles business logic, the Repository layer handles database queries, and the DB layer manages connections. This separation means if I need to change the database, I only touch the Repository layer. If I change the API format, I only touch the API layer. It follows the Single Responsibility Principle and makes the code maintainable and testable."*

---

### "How would you scale this system?"
> *"Currently it's a single-instance setup. To scale: I'd run multiple FastAPI instances behind a load balancer (like Nginx), since our app is stateless — the driver is a singleton per instance, Redis is external shared state. For Neo4j, I'd use Neo4j's clustering/read-replica setup to distribute read queries. Redis can be clustered as well. The Docker Compose setup would be migrated to Kubernetes for production orchestration."*

---

## SECTION 7: Cypher Queries to Know

Practice running these in the Neo4j Browser (`http://localhost:7474`):

```cypher
-- See the schema (node labels and relationship types)
CALL db.schema.visualization()

-- Count all users and connections
MATCH (u:User) RETURN count(u) AS total_users
MATCH ()-[:CONNECTED]-() RETURN count(*)/2 AS total_connections

-- Find shortest path between two users
MATCH (a:User {id: '0'}), (b:User {id: '150'})
MATCH path = shortestPath((a)-[:CONNECTED*]-(b))
RETURN path

-- Find the most connected users (top 10 hubs)
MATCH (u:User)-[:CONNECTED]-()
RETURN u.id, count(*) AS connections
ORDER BY connections DESC
LIMIT 10

-- Find friends-of-friends for user '0'
MATCH (u:User {id: '0'})-[:CONNECTED]-(friend)-[:CONNECTED]-(fof)
WHERE fof.id <> '0' AND NOT (u)-[:CONNECTED]-(fof)
RETURN fof.id, count(friend) AS mutual_count
ORDER BY mutual_count DESC
LIMIT 10

-- Visualize a sample of the social graph
MATCH (u:User)-[r:CONNECTED]-(friend)
RETURN u, r, friend
LIMIT 50
```

---

## SECTION 8: Things to Demo in an Interview

- [ ] **Docker Compose start:** `docker compose up -d` — show all 3 containers starting with health checks
- [ ] **Swagger UI:** Open `http://localhost:5000/docs` — show auto-generated docs
- [ ] **Create a user:** POST /api/v1/users with name and email
- [ ] **Find a path:** GET /api/v1/path/0/150 — show the JSON response
- [ ] **Show caching:** Call the same endpoint twice — second call has `"cached": true`
- [ ] **Friend suggestions:** GET /api/v1/suggestions/0 — show ranked suggestions
- [ ] **Neo4j Browser:** Open `http://localhost:7474` — run a visual query showing the graph
- [ ] **Show logs:** `docker compose logs -f api` — show JSON structured logs in real time

---

## SECTION 9: Quick Reference Card

| Concept | One-Line Explanation |
|---|---|
| Graph | Data structure with nodes (users) and edges (friendships) |
| BFS | Explores graph level by level, guarantees shortest path |
| Bidirectional BFS | BFS from both ends simultaneously, much faster |
| Neo4j shortestPath | Cypher function that runs bidirectional BFS natively |
| Redis TTL | Automatic expiry of cached data after N seconds |
| Singleton | One shared instance (our Neo4j driver) |
| Repository Pattern | Isolate all DB queries in one layer |
| Dependency Injection | FastAPI injects the driver into route functions via Depends() |
| Pydantic | Automatic request/response validation using Python type hints |
| Docker Volume | Persistent storage for containers (your data survives restarts) |
| Healthcheck | Docker tests if a service is ready before starting dependent services |
| SETEX | Redis command: SET key with EXpiry time |
| Bolt Protocol | Neo4j's binary connection protocol (port 7687) |
| ASGI | Async Server Gateway Interface (what FastAPI and uvicorn use) |
| Lifespan | FastAPI context manager for startup/shutdown logic |
