from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.neo4j_db import test_connection

# Will import routes later
# from app.api import routes_users, routes_graph

app = FastAPI(
    title="Social Network Pathfinding API",
    description="A highly scalable pathfinding engine using Neo4j and Redis.",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Check if the API is running.
    """
    return {"status": "ok", "message": "API is running"}

@app.get("/db-check")
def db_check():
    return {"neo4j": test_connection()}


# TODO: Include routers
# app.include_router(routes_users.router)
# app.include_router(routes_graph.router)

if __name__ == "__main__":
    import uvicorn
    # This allows running `python app/main.py` directly for development
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=True)
