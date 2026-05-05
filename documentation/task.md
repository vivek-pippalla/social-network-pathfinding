# Task Tracker: 5-Day Pathfinding Engine Rebuild

## Day 1: Infrastructure & Skeleton
- [x] Delete old `src/` mock files.
- [x] Create new folder structure (`app/api`, `app/core`, `app/services`, `app/db`).
- [x] Initialize `main.py` (FastAPI entry point).
- [x] Update `requirements.txt` with FastAPI, Neo4j, Redis.
- [x] Update `docker-compose.yml` to include Neo4j and Redis.

## Day 2: Data Layer & Models
- [ ] Implement Neo4j connection manager (`app/db/neo4j_db.py`).
- [ ] Create Pydantic schemas (`app/models/schemas.py`).
- [ ] Implement User endpoints (POST, GET).
- [ ] Implement Connection endpoints (POST, DELETE).

## Day 3: Pathfinding & Caching
- [ ] Write Neo4j Cypher query for shortest path.
- [ ] Create Pathfinding endpoint.
- [ ] Implement Redis connection manager (`app/db/redis_cache.py`).
- [ ] Add caching logic to Pathfinding endpoint.

## Day 4: AI Recommendations & Polish
- [ ] Create Recommendation endpoint (Triadic Closure).
- [ ] Implement global exception handling (`app/core/exceptions.py`).
- [ ] Configure logging.

## Day 5: Testing & Resume Readiness
- [ ] Set up `pytest` and write unit tests.
- [ ] Write data seeding script.
- [ ] Rewrite `README.md` with architecture details.
