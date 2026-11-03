# Social Network Pathfinding Engine (Cloud-Native Edition)

> **Status:** Reconstruction is underway. Existing feature, deployment, and performance claims are being re-verified; treat them as unverified until the relevant phase records evidence.

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

Given two user IDs, the engine computes a bounded shortest path through the social graph using Neo4j's built-in `shortestPath()`. Results use a versioned Redis cache; latency has not been benchmarked against a live stack.

The system also provides **"People You May Know"** recommendations — ranking friend-of-friend suggestions by mutual friend count using the Triadic Closure algorithm — available through an authenticated endpoint for any user and a personalized `/me` endpoint derived from your JWT token.

---

## Key Features

| Domain | Feature | Description |
|---|---|---|
| **Graph Algorithm** | **Shortest Path** | Bidirectional BFS with hop counts between any two nodes in <150 ms |
| **Caching** | **Versioned Redis path cache** | Canonical path keys with graph-version invalidation and short negative caching |
| **Recommendations** | **Friend Suggestions** | Triadic closure ranking friends-of-friends by mutual connections |
| **Dataset** | **SNAP Graph Ingestion** | Checksum-verified download, validated parsing, additive Neo4j batches |
| **Security & Config** | **Host Secret Isolation** | Protected `.env.prod` (chmod 600) outside Git; unexposed internal database ports |
| **Observability** | **CloudWatch & Prometheus** | Dual-tier monitoring: CloudWatch JSON logs + Prometheus/Grafana metrics |
| **Identity & Access** | **JWT & Least-Privilege IAM** | OAuth2 password flow with bcrypt + fine-grained AWS IAM roles & policies |
| **DevOps & CI/CD** | **GitHub Actions OIDC** | Keyless AWS authentication building and pushing Docker images to ECR |
| **Containerization** | **Production Docker Compose** | Isolated internal bridge network; Neo4j & Redis ports shielded from public host |

---

## Tech Stack & AWS Services

### Core Application
- **Language & Framework:** Python 3.11, FastAPI, Pydantic v2
- **Databases:** Neo4j 5.12 (Graph DB), Redis 7 (rate limiting; path cache planned for Phase 6)
- **Security:** JWT (python-jose), bcrypt (passlib)
- **Monitoring:** Prometheus, Grafana, Vis.js graph UI

### AWS Cloud Architecture
- **Amazon EC2 (`t3.medium`):** Single-host container runtime running Dockerized FastAPI, Neo4j, and Redis.
- **Amazon S3:** Private bucket hosting raw gzipped graph datasets with SSE-AES256.
- **AWS IAM:** Strict least-privilege instance roles and GitHub Actions trust policies.
- **Amazon CloudWatch:** Centralized structured JSON log shipping with stream auto-naming and retention.
- **Amazon ECR:** Private container registry for multi-stage production Docker images.
- **GitHub Actions:** CI test execution with pytest + OIDC-based deployment pipeline.

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
 │  │  Security Group: Inbound 22 (SSH Admin), 80 (HTTP), 443 (HTTPS)                │   │
 │  │                                                                                │   │
 │  │   ┌────────────────────────────────────────────────────────────────────────┐   │   │
 │  │   │ Docker Network: internal-network (Bridge)                              │   │   │
 │  │   │                                                                        │   │   │
 │  │   │   ┌────────────────────────┐        ┌───────────────────────────────┐  │   │   │
 │  │   │   │   FastAPI App (ECR)    │───────▶│   Redis 7 (rate limiting)     │  │   │   │
 │  │   │   │   (Internal port 5000) │        │      (Internal port 6379)     │  │   │   │
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
 │ 1. Pytest suite (API, S3 ingestion, CloudWatch logging, deployment, Caddy config)       │
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

### Public Endpoints (No JWT Required)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Application health check |
| `GET` | `/health/ready` | Dependency readiness check |
| `POST` | `/api/v1/auth/register` | Register new user account (returns JWT) |
| `POST` | `/api/v1/auth/token` | Login via OAuth2 password flow (returns JWT) |

### Protected Endpoints (Bearer JWT Required)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/users/{user_id}` | Retrieve public user profile |
| `GET` | `/api/v1/users/search?q=` | Search user profiles by name |
| `GET` | `/api/v1/path/{user1}/{user2}` | Bounded shortest path between two users |
| `GET` | `/api/v1/users/{user_id}/suggestions` | Paged friend-of-friend suggestions for a user |
| `GET` | `/api/v1/suggestions/me` | Paged suggestions for the authenticated user |
| `GET` | `/api/v1/users/me` | Retrieve authenticated user's profile |
| `PUT` | `/api/v1/users/me` | Update authenticated user's profile |
| `GET` | `/api/v1/friends` | List authenticated user's friends |
| `POST` | `/api/v1/friends/{friend_id}` | Add a friend to authenticated user |
| `DELETE` | `/api/v1/friends/{friend_id}` | Remove a friend connection |
| `GET` | `/api/v1/users/{user_id}/mutual` | List mutual friends with a user |

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
# Downloads the official SNAP archive if needed, verifies its checksum, and imports it additively.
docker compose run --rm api python -m app.cli ingest
```

### 4. Access Services
- **Web UI & Graph Visualizer:** `http://localhost:5000`
- **Interactive Swagger Docs:** `http://localhost:5000/docs`
- **Neo4j Browser:** `http://localhost:7474`
- **Prometheus Metrics:** `http://localhost:9090`
- **Grafana Dashboards:** `http://localhost:3000` (`admin` / `admin`)

---

## Running Tests

Unit tests run offline. Integration tests use real Neo4j and Redis and are marked separately:

```bash
# Run the complete test suite
pytest tests/ -v
```

**Test Coverage Highlights:**
- **API routes & Auth:** JWT encoding/decoding, token expiry, password hashing, 401 guards, friend management.
- **Graph & pathfinding:** Neo4j path queries and hop counts. Redis path caching is planned for Phase 6.
- **Dataset ingestion:** checksum validation, parser rejection counts, reset confirmation, idempotent writes, and cache-version updates.
- **CloudWatch Logging:** Handler attachment, duplicate prevention, structured JSON formatting.
- **Deployment & Rollback Logic:** Success states, healthcheck timeout, automated rollback restoration, critical rollback failure reporting.

---

## Historical AWS Deployment Material

The previous AWS guide and deployment files are inactive historical references. They have not been retested since the AWS account closed:

👉 **[Inactive AWS deployment reference](deploy/aws/legacy/README.md)**

---

## Project Structure

```text
social-network-pathfinding/
├── app/                         # FastAPI application and ingestion CLI
├── data/                        # SNAP source citation and checksum details
├── deploy/aws/legacy/           # Inactive historical AWS deployment material
├── scripts/test-infra.sh        # Isolated real-service test stack helper
├── tests/                       # Automated test suite
├── docker-compose.yml           # Local development stack
├── docker-compose.prod.yml      # Production-like stack
└── requirements*.txt            # Runtime, development, and optional AWS pins
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.
