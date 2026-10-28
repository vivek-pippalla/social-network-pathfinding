# Social Network Pathfinding Engine (Cloud-Native Edition)

[![CI/CD Pipeline](https://github.com/vivek-pippalla/social-network-pathfinding/actions/workflows/ci.yml/badge.svg)](https://github.com/vivek-pippalla/social-network-pathfinding/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688.svg)](https://fastapi.tiangolo.com)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.12-blue.svg)](https://neo4j.com/)
[![Redis](https://img.shields.io/badge/Redis-7.0-red.svg)](https://redis.io/)
[![AWS](https://img.shields.io/badge/AWS-EC2%20%7C%20S3%20%7C%20IAM%20%7C%20CloudWatch%20%7C%20ECR-orange.svg)](https://aws.amazon.com/)

A production-grade, cloud-native social graph engine that computes the **shortest connection path** between users in a social graph (similar to LinkedIn's *"You and Satya Nadella are 3 degrees apart"*).

Built with **FastAPI**, **Neo4j**, and **Redis**, backed by the real-world [Stanford SNAP Facebook dataset](https://snap.stanford.edu/data/ego-Facebook.html) (4,039 users · 88,234 connections). Deployed on **AWS** with **EC2, S3, IAM, CloudWatch, and ECR**, with fully automated CI/CD via **GitHub Actions using AWS OIDC federation**.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Tech Stack & AWS Services](#tech-stack--aws-services)
- [System Architecture](#system-architecture)
- [Cloud Infrastructure & Security](#cloud-infrastructure--security)
- [API Reference](#api-reference)
- [Local Quickstart](#local-quickstart)
- [Running Tests](#running-tests)
- [AWS Production Deployment](#aws-production-deployment)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [License](#license)

---

## Overview

Given two user IDs, the engine computes the shortest path through the social graph using Neo4j's built-in **bidirectional BFS** (`shortestPath()`). Results are cached in Redis using order-independent keys so repeated queries return in under 10 ms.

The system also provides **"People You May Know"** recommendations — ranking friend-of-friend suggestions by mutual friend count using the Triadic Closure algorithm — available as both a public endpoint and a personalized `/me` variant derived from your JWT token.

---

## Key Features

| Domain | Feature | Description |
|---|---|---|
| **Graph Algorithm** | **Shortest Path** | Bidirectional BFS with hop counts between any two nodes in <150 ms |
| **Caching** | **Redis Cache-Aside** | Order-independent cache keys (`path:min:max`); cache hits return in <10 ms |
| **Recommendations** | **Friend Suggestions** | Triadic closure ranking friends-of-friends by mutual connections |
| **Cloud Storage** | **S3 Dataset Ingestion** | Robust, private S3 ingestion with data validation and URL/local fallbacks |
| **Security & Config** | **Host Secret Isolation** | Protected `.env.prod` (chmod 600) outside Git; unexposed internal database ports |
| **Observability** | **CloudWatch & Prometheus** | Dual-tier monitoring: CloudWatch JSON logs + Prometheus/Grafana metrics |
| **Identity & Access** | **JWT & Least-Privilege IAM** | OAuth2 password flow with bcrypt + fine-grained AWS IAM roles & policies |
| **DevOps & CI/CD** | **GitHub Actions OIDC** | Keyless AWS authentication building and pushing Docker images to ECR |
| **Containerization** | **Production Docker Compose** | Isolated internal bridge network; Neo4j & Redis ports shielded from public host |

---

## Tech Stack & AWS Services

### Core Application
- **Language & Framework:** Python 3.11, FastAPI, Pydantic v2
- **Databases:** Neo4j 5.12 (Graph DB), Redis 7 (In-Memory Cache)
- **Security:** JWT (python-jose), bcrypt (passlib)
- **Monitoring:** Prometheus, Grafana, Vis.js graph UI

### AWS Cloud Architecture
- **Amazon EC2 (`t3.medium`):** Single-host container runtime running Dockerized FastAPI, Neo4j, and Redis.
- **Amazon S3:** Private bucket hosting raw gzipped graph datasets with SSE-AES256.
- **AWS IAM:** Strict least-privilege instance roles and GitHub Actions trust policies.
- **Amazon CloudWatch:** Centralized structured JSON log shipping with stream auto-naming and retention.
- **Amazon ECR:** Private container registry for multi-stage production Docker images.
- **GitHub Actions:** CI test execution (51 unit tests) + OIDC-based deployment pipeline.

---

## System Architecture

### AWS Cloud Production Layout

```
                                    AWS Cloud (ap-south-1)
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                                                                                        │
 │  ┌──────────────────────┐             ┌───────────────────────────────────────────┐    │
 │  │      Amazon S3       │             │           Amazon CloudWatch Logs          │    │
 │  │  (Private Datasets)  │             │   (/social-network-pathfinding/app)       │    │
 │  └──────────┬───────────┘             └─────────────────────▲─────────────────────┘    │
 │             │ (IAM Auth / seed_data.py)                     │ (Structured JSON logs)   │
 │             ▼                                               │                          │
 │  ┌──────────────────────────────────────────────────────────┴────────────────────┐   │
 │  │ Amazon EC2 (t3.medium: 2 vCPU, 4GB RAM + 2GB Swap)                             │   │
 │  │                                                                                │   │
 │  │  Security Group: Inbound 22 (SSH Admin), Inbound 5000 (FastAPI Web)            │   │
 │  │                                                                                │   │
 │  │   ┌────────────────────────────────────────────────────────────────────────┐   │   │
 │  │   │ Docker Network: internal-network (Bridge)                              │   │   │
 │  │   │                                                                        │   │   │
 │  │   │   ┌────────────────────────┐        ┌───────────────────────────────┐  │   │   │
 │  │   │   │   FastAPI App (ECR)    │───────▶│      Redis 7 Cache (LRU)      │  │   │   │
 │  │   │   │   (Port 5000 -> Host)  │        │      (Internal port 6379)     │  │   │   │
 │  │   │   └──────────┬─────────────┘        │      (Shielded from Host)     │  │   │   │
 │  │   │              │                      └───────────────────────────────┘  │   │   │
 │  │   │              ▼                                                         │   │   │
 │  │   │   ┌────────────────────────┐                                           │   │   │
 │  │   │   │   Neo4j 5.12 Graph DB  │                                           │   │   │
 │  │   │   │  (Internal 7687, 7474) │                                           │   │   │
 │  │   │   │  (Shielded from Host)  │                                           │   │   │
 │  │   │   └────────────────────────┘                                           │   │   │
 │  │   └────────────────────────────────────────────────────────────────────────┘   │   │
 │  └────────────────────────────────────────▲───────────────────────────────────────┘   │
 │                                            │                                          │
 │  ┌──────────────────────┐                  │ (ecr pull via Instance Role)             │
 │  │      Amazon ECR      │──────────────────┘                                          │
 │  │ (social-network-api) │                                                             │
 │  └──────────▲───────────┘                                                             │
 │             │ (docker push via OIDC)                                                  │
 └─────────────┼─────────────────────────────────────────────────────────────────────────┘
               │
 ┌─────────────┴─────────────────────────────────────────────────────────────────────────┐
 │ GitHub Actions (CI/CD Pipeline)                                                        │
 │ 1. Pytest Unit Tests (45 tests: API, S3 ingestion, CloudWatch logging, Friends)        │
 │ 2. Build multi-stage Docker image                                                     │
 │ 3. AWS OIDC STS AssumeRoleWithWebIdentity (Keyless) -> Push to ECR                    │
 │ 4. SSH to EC2 -> Pull latest ECR image -> Update containers -> Healthcheck            │
 └───────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Cloud Infrastructure & Security

1. **Keyless AWS Authentication (OIDC):** GitHub Actions generates short-lived STS tokens directly using `AssumeRoleWithWebIdentity`, completely avoiding hardcoded AWS access keys.
2. **Network Isolation:** Neo4j (7474, 7687) and Redis (6379) ports are unexposed to the host machine in production. They communicate exclusively over Docker's internal virtual bridge network.
3. **Host Secret Isolation:** Production secrets are isolated in a server-side `.env.prod` file with `chmod 600`, preventing exposure to Git and Docker image layers.
4. **Resilient Logging:** CloudWatch Log streaming (`watchtower`) handles transient AWS errors gracefully, always guaranteeing local stdout stream availability.

---

## API Reference

### Public Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Application health check |
| `POST` | `/api/v1/auth/register` | Register new user account (returns JWT) |
| `POST` | `/api/v1/auth/token` | Login via OAuth2 password flow (returns JWT) |
| `GET` | `/api/v1/path/{user1}/{user2}` | Shortest path between two users (cached in Redis) |
| `GET` | `/api/v1/suggestions/{user_id}` | Friend-of-friend suggestions for any user ID |
| `GET` | `/api/v1/users/{user_id}` | Retrieve public user profile |
| `GET` | `/api/v1/users/search?q=` | Search user profiles by name |

### Protected Endpoints (Bearer JWT Required)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/suggestions/me` | Personalized friend suggestions for authenticated user |
| `GET` | `/api/v1/users/me` | Retrieve authenticated user's profile |
| `PUT` | `/api/v1/users/me` | Update authenticated user's profile |
| `POST` | `/api/v1/connections` | Create a friendship connection between two users |
| `POST` | `/friends/{friend_id}` | Add a friend to authenticated user |
| `DELETE` | `/friends/{friend_id}` | Remove a friend connection |

---

## Local Quickstart

### Prerequisites
- Docker & Docker Compose
- Python 3.11

### 1. Clone & Configure
```bash
git clone https://github.com/vivek-pippalla/social-network-pathfinding.git
cd social-network-pathfinding
cp .env.example .env
```

### 2. Start Local Containers
```bash
docker compose up --build -d
```

### 3. Seed Dataset
```bash
# Ingests from local file / URL / S3 automatically with full record validation
docker exec -it social-network-api python scripts/seed_data.py
```

### 4. Access Services
- **Web UI & Graph Visualizer:** `http://localhost:5000`
- **Interactive Swagger Docs:** `http://localhost:5000/docs`
- **Neo4j Browser:** `http://localhost:7474`
- **Prometheus Metrics:** `http://localhost:9090`
- **Grafana Dashboards:** `http://localhost:3000` (`admin` / `admin`)

---

## Running Tests

The test suite runs 100% offline with zero live infrastructure dependencies by mocking database and AWS SDK calls:

```bash
# Run all 51 unit tests
pytest tests/ -v
```

**Test Coverage Highlights:**
- **API routes & Auth:** JWT encoding/decoding, token expiry, password hashing, 401 guards, friend management.
- **Graph & Cache-aside:** Redis cache hits, Neo4j cache misses, hop counts.
- **S3 Dataset Pipeline:** S3 downloads, ClientError handling, record validation, URL fallbacks, production failure enforcement.
- **CloudWatch Logging:** Handler attachment, duplicate prevention, structured JSON formatting.
- **Deployment & Rollback Logic:** Success states, healthcheck timeout, automated rollback restoration, critical rollback failure reporting.

---

## AWS Production Deployment

For the complete step-by-step AWS deployment walkthrough, IAM policies, and cost mitigation instructions, refer to:

👉 **[AWS Production Deployment Guide](documentation/aws_deployment_guide.md)**

---

## Project Structure

```
social-network-pathfinding/
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI/CD with AWS OIDC federation
├── app/
│   ├── api/                       # Router layer (REST endpoints)
│   ├── core/                      # Config, auth, exceptions, logging
│   │   ├── config.py              # Pydantic v2 settings
│   │   └── logging_config.py      # CloudWatch + structured JSON logging
│   ├── db/                        # Neo4j & Redis connection singletons
│   ├── models/                    # Pydantic request/response schemas
│   ├── repositories/              # Cypher query & graph repository layer
│   ├── services/                  # Business logic & algorithms
│   │   ├── pathfinder.py          # Shortest path & triadic closure
│   │   ├── s3_service.py          # S3 dataset downloader & edge validator
│   │   └── user_service.py        # User profile management
│   ├── static/                    # Frontend UI (HTML5 + Vis.js graph demo)
│   └── main.py                    # FastAPI application entrypoint
├── infra/
│   └── iam/                       # Least-privilege IAM policy documents
│       ├── ec2-instance-policy.json
│       ├── ec2-trust-policy.json
│       ├── github-actions-policy.json
│       └── github-oidc-trust-policy.json
├── scripts/
│   ├── deploy_prod.sh             # EC2 deployment automation script
│   ├── ec2_setup.sh               # Host setup (Docker, swap, dependencies)
│   ├── ecr_push.sh                # Docker build & push to AWS ECR
│   └── seed_data.py               # Dataset ingestion pipeline (S3/URL/Local)
├── tests/
│   ├── conftest.py                # Pytest mock fixtures
│   ├── test_api.py                # Core API & auth test suite (31 tests)
│   ├── test_cloudwatch_logging.py # CloudWatch integration test suite (5 tests)
│   ├── test_deploy_script.py      # Deployment & automated rollback test suite (6 tests)
│   └── test_s3_ingestion.py       # S3 dataset ingestion test suite (9 tests)
├── documentation/
│   └── aws_deployment_guide.md    # Comprehensive AWS deployment guide
├── docker-compose.yml             # Local development stack
├── docker-compose.prod.yml        # Hardened production stack for EC2
├── Dockerfile                     # Multi-stage production container
└── requirements.txt               # Locked dependencies
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.
