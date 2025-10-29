# Distributed Social Network Pathfinding Engine

🚀 A high-performance, scalable distributed system for finding shortest paths (degrees of separation) between users in massive social networks.

## 🌟 Project Overview

This project implements a sophisticated distributed pathfinding engine designed to solve one of the core problems in social networking: efficiently finding the shortest connection path between any two users in a graph with millions or billions of nodes and edges.

### 🏗️ Key Features

- **Distributed Graph Database**: Sharded graph storage across multiple nodes  
- **Bidirectional BFS Algorithm**: Optimized pathfinding with O(b^(d/2)) complexity  
- **High-Performance Caching**: Redis-based LRU cache with intelligent invalidation  
- **REST API**: Production-ready API with comprehensive endpoints  
- **Real-time Updates**: Dynamic graph updates with eventual consistency  
- **Containerized Deployment**: Docker and Kubernetes-ready  
- **Monitoring**: Built-in metrics and observability via Prometheus & Grafana  

### 🎯 Performance Targets

- **Sub-100ms** response times for 3-degree path lookups  
- **10+ million** user profiles supported  
- **High availability** with fault tolerance  
- **Linear scalability** through horizontal sharding  

## 🏛️ Architecture

### 1. Distributed Graph Database Layer
- **Edge-cut sharding** strategy for optimal load distribution  
- **Consistent hashing** for user placement across shards  
- **Cross-shard reference handling** for efficient queries  
- **TigerGraph/Neo4j-compatible interface**  

### 2. Intelligent Pathfinding Service
- **Bidirectional BFS** implementation  
- **Search space reduction** from O(b^d) to O(2×b^(d/2))  
- **Distributed query execution** across shards  
- **Path result caching** for repeated lookups  

### 3. High-Performance Caching Layer
- **Distributed LRU cache** using Redis cluster  
- **Intelligent cache invalidation** on graph updates  
- **TTL-based expiration** for cache freshness  

### 4. Dynamic Graph Updates
- **Message queue-based** real-time update model (Kafka optional)  
- **Eventual consistency** across distributed nodes  
- **Bulk operations** for efficiency  

---

## 🚦 Quick Start

### Prerequisites

- **Python 3.11+**  
- **Docker & Docker Compose**  
- **Redis** (for caching)  
- **MongoDB** (for persistent storage)

### Installation
bash
git clone <repository-url>
cd social-network-pathfinding
pip install -r requirements.txt

## Run API locally
   python api_server.py

## Docker Deployment
   docker-compose up --build

## Access:
    API → http://localhost:5000
    Monitoring (Grafana) → http://localhost:3000
    Metrics (Prometheus) → http://localhost:9090

## 📡 API Reference
### Find Path Between Users

POST /api/v1/path
Content-Type: application/json
{
  "start_user_id": "user123",
  "target_user_id": "user456",
  "use_cache": true
}

### Add New User

POST /api/v1/users
{
  "username": "john_doe",
  "email": "john@example.com"
}

### Create Connection

POST /api/v1/connections
{
  "from_user_id": "user123",
  "to_user_id": "user456"
}

### Service Statistics
GET /api/v1/stats

### Health Check
GET /health

🏗️ System Design Highlights
**Database Sharding**
**Edge-Cut Sharding → simplicity, scalability, locality**
**Consistent hashing → smooth scaling**

Algorithm
**Bidirectional BFS → exponential performance gain**
**Lower memory usage and better parallelism**

Caching
**Path-specific LRU cache**
**Fast invalidation on updates**
**Distributed and TTL-based**
