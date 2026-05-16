# Project Execution Plan: Pathfinding Engine

---

##  Requirements Specification

### Functional Requirements (FR)
1. **User Management:** API to create users and fetch user details.
2. **Connection Management:** API to create and remove directed/undirected connections (friendships/follows) between users.
3. **Pathfinding (Core):** API to find the shortest path (degrees of separation) between User A and User B.
4. **Suggestions (AI/Algorithm):** API to suggest new connections based on mutual friends or graph proximity.

### Non-Functional Requirements (NFR)
1. **Performance:** Sub-100ms response time for path lookups via Redis caching.
2. **Scalability:** Dockerized components (API, DB, Cache) for horizontal scaling.
3. **Observability:** Centralized logging and clean error handling.
4. **Documentation:** Auto-generated Swagger/OpenAPI docs via FastAPI and a pristine README.

---

## Milestone Blocks

### Block 1: Infrastructure & Skeleton
**Goal:** Tear down the old mocks and set up the foundation.
*   **Tasks:**
    *   Delete the flat `src/` mock files.
    *   Create the production folder structure (`app/api`, `app/core`, `app/services`, `app/db`).
    *   Initialize the FastAPI application and configure the server.
    *   Update `docker-compose.yml` to pull Neo4j and Redis images.
    *   Update `requirements.txt` (`fastapi`, `uvicorn`, `neo4j`, `redis`).
*   **Validation:** Docker compose spins up all 3 containers, and FastAPI serves a health check at `localhost:5000/health`.

### Block 2: Data Layer & Relationships
**Goal:** Connect to the databases and build the basic social graph.
*   **Tasks:**
    *   Implement the Neo4j connection manager (`app/db/neo4j_db.py`).
    *   Create Pydantic models for User and Connection schemas.
    *   Build the User Endpoints: `POST /users`, `GET /users/{id}`.
    *   Build the Connection Endpoints: `POST /connections`, `DELETE /connections`.
*   **Validation:** You can use Postman/Swagger to create users and link them together in the Neo4j database.

### Block 3: Pathfinding & Caching
**Goal:** Implement the core algorithm and make it blazing fast.
*   **Tasks:**
    *   Write the Cypher query in Neo4j to find the shortest path between two nodes.
    *   Create the Pathfinding Endpoint: `GET /path/{start_user}/{target_user}`.
    *   Implement Redis connection manager (`app/db/redis_cache.py`).
    *   Add caching logic: Before querying Neo4j, check if the path `A->B` exists in Redis. If found, return instantly. If not, query Neo4j and store in Redis with a TTL (Time To Live).
*   **Validation:** Querying the same path twice shows a 10x speedup on the second request due to a cache hit.

### Block 4: AI Recommendations & Polish
**Goal:** Add the "Wow Factor" for startups and ensure edge cases are handled.
*   **Tasks:**
    *   Create the Recommendation Endpoint: `GET /suggestions/{user_id}`.
    *   Write a graph query to find "Friends of Friends" who are not yet connected (Triadic Closure).
    *   Implement global exception handling (e.g., returning proper 404s if a user doesn't exist, instead of crashing).
*   **Validation:** Calling the suggestions endpoint returns a smart list of users to connect with.

### Block 5: Testing & Resume Readiness
**Goal:** Prove the code works and make it look professional on GitHub.
*   **Tasks:**
    *   Set up `pytest` and write unit tests for the endpoints.
    *   Write a data seeding script to generate 1,000 dummy users and random connections so recruiters can test it immediately.
    *   Rewrite the `README.md`. It must explain *Why Neo4j*, explain the architecture, and include a diagram.
*   **Validation:** Tests pass (`pytest`), and the GitHub repository is pristine, heavily documented, and ready to be linked on a resume.
