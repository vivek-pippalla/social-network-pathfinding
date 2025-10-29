#!/usr/bin/env python3
"""
Distributed Social Network Pathfinding Engine
Main application entry point with demo functionality
"""
import sys
import os
import time
import json
import random
from typing import List, Tuple
import threading
import argparse

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import our components (simplified for demo)
from collections import defaultdict, deque
import uuid
from datetime import datetime

class SocialNetworkDemo:
    """
    Demo implementation of the distributed social network pathfinding engine
    Combines all components with realistic test data
    """

    def __init__(self):
        print("🚀 Initializing Distributed Social Network Pathfinding Engine...")

        # Initialize core components
        self.graph_db = self._create_demo_database()
        self.pathfinder = self._create_pathfinder()
        self.cache = self._create_cache()

        # Demo data
        self.users = {}
        self.connections = defaultdict(set)

        print("✅ All components initialized successfully!")

    def _create_demo_database(self):
        """Create demo graph database"""
        print("📊 Setting up graph database with sharding...")

        class MockGraphDB:
            def __init__(self):
                self.users = {}
                self.connections = defaultdict(set)
                self.query_count = 0

            def add_user(self, username, email, user_id=None):
                if user_id is None:
                    user_id = str(uuid.uuid4())
                self.users[user_id] = {
                    'user_id': user_id,
                    'username': username,
                    'email': email,
                    'created_at': datetime.now().isoformat()
                }
                return user_id

            def add_connection(self, from_user, to_user):
                if from_user in self.users and to_user in self.users:
                    self.connections[from_user].add(to_user)
                    self.connections[to_user].add(from_user)
                    return True
                return False

            def get_connections(self, user_id):
                self.query_count += 1
                return self.connections.get(user_id, set())

            def user_exists(self, user_id):
                return user_id in self.users

            def get_database_stats(self):
                total_connections = sum(len(conns) for conns in self.connections.values()) // 2
                return {
                    'total_users': len(self.users),
                    'total_connections': total_connections,
                    'query_count': self.query_count,
                    'average_connections': total_connections / max(len(self.users), 1)
                }

        return MockGraphDB()

    def _create_pathfinder(self):
        """Create bidirectional BFS pathfinder"""
        print("🔍 Setting up bidirectional BFS pathfinding...")

        class MockPathfinder:
            def __init__(self, graph_db):
                self.graph_db = graph_db
                self.max_depth = 6

            def find_shortest_path(self, start_user, target_user):
                start_time = time.time()

                if start_user == target_user:
                    return self._create_result([start_user], 1, start_time, True)

                if not (self.graph_db.user_exists(start_user) and 
                       self.graph_db.user_exists(target_user)):
                    return self._create_result(None, 0, start_time, False)

                # Simplified BFS implementation
                path = self._bfs_search(start_user, target_user)
                found = path is not None
                nodes_explored = random.randint(50, 500)  # Mock

                return self._create_result(path, nodes_explored, start_time, found)

            def _bfs_search(self, start, target):
                """Simplified BFS for demo"""
                if start == target:
                    return [start]

                queue = deque([(start, [start])])
                visited = {start}

                for _ in range(1000):  # Limit iterations
                    if not queue:
                        break

                    current, path = queue.popleft()

                    if len(path) > self.max_depth:
                        continue

                    neighbors = self.graph_db.get_connections(current)
                    for neighbor in neighbors:
                        if neighbor == target:
                            return path + [neighbor]

                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append((neighbor, path + [neighbor]))

                return None

            def _create_result(self, path, nodes_explored, start_time, found):
                """Create pathfinding result object"""
                class PathResult:
                    def __init__(self):
                        self.path = path
                        self.found = found
                        self.nodes_explored = nodes_explored
                        self.execution_time_ms = (time.time() - start_time) * 1000
                        self.distance = len(path) - 1 if path else -1

                return PathResult()

        return MockPathfinder(self.graph_db)

    def _create_cache(self):
        """Create LRU cache"""
        print("💾 Setting up distributed LRU cache...")

        class MockCache:
            def __init__(self):
                self.cache = {}
                self.hit_count = 0
                self.miss_count = 0

            def get(self, key):
                if key in self.cache:
                    self.hit_count += 1
                    return self.cache[key]
                self.miss_count += 1
                return None

            def put(self, key, value):
                self.cache[key] = value

            def get_stats(self):
                total = self.hit_count + self.miss_count
                return {
                    'size': len(self.cache),
                    'hit_count': self.hit_count,
                    'miss_count': self.miss_count,
                    'hit_rate': self.hit_count / total if total > 0 else 0.0
                }

        return MockCache()

    def generate_demo_data(self, num_users: int = 1000, avg_connections: int = 5):
        """Generate realistic social network demo data"""
        print(f"🎲 Generating demo data: {num_users} users with ~{avg_connections} connections each...")

        # Generate users
        user_ids = []
        for i in range(num_users):
            username = f"user_{i:04d}"
            email = f"user{i}@example.com"
            user_id = self.graph_db.add_user(username, email)
            user_ids.append(user_id)

        # Generate connections (preferential attachment model)
        print("🔗 Creating social connections...")
        total_connections = 0

        for i, user_id in enumerate(user_ids):
            # Number of connections for this user (Poisson-like distribution)
            num_connections = max(1, int(random.gammavariate(2, avg_connections/2)))

            # Connect to random users with preference for earlier users (more connected)
            potential_connections = user_ids[:i] + user_ids[i+1:]

            if potential_connections:
                # Weight earlier users higher (preferential attachment)
                weights = [max(1, len(user_ids) - j) for j in range(len(potential_connections))]

                connections_to_make = min(num_connections, len(potential_connections))
                selected_users = random.choices(
                    potential_connections, 
                    weights=weights, 
                    k=connections_to_make
                )

                for target_user in selected_users:
                    if self.graph_db.add_connection(user_id, target_user):
                        total_connections += 1

        stats = self.graph_db.get_database_stats()
        print(f"✅ Generated {stats['total_users']} users and {stats['total_connections']} connections")
        print(f"📈 Average connections per user: {stats['average_connections']:.2f}")

        return user_ids

    def run_performance_benchmark(self, user_ids: List[str], num_queries: int = 100):
        """Run performance benchmark on pathfinding"""
        print(f"⚡ Running performance benchmark with {num_queries} queries...")

        results = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'total_time_ms': 0,
            'average_time_ms': 0,
            'min_time_ms': float('inf'),
            'max_time_ms': 0,
            'paths_found': 0,
            'average_path_length': 0,
            'cache_stats': None
        }

        path_lengths = []
        query_times = []

        for i in range(num_queries):
            # Select random user pair
            start_user = random.choice(user_ids)
            target_user = random.choice(user_ids)

            # Avoid self-queries
            while target_user == start_user:
                target_user = random.choice(user_ids)

            # Execute pathfinding query
            start_time = time.time()
            result = self.pathfinder.find_shortest_path(start_user, target_user)
            query_time = (time.time() - start_time) * 1000

            # Update results
            results['total_queries'] += 1
            query_times.append(query_time)

            if result.found:
                results['successful_queries'] += 1
                results['paths_found'] += 1
                path_lengths.append(result.distance)
            else:
                results['failed_queries'] += 1

            # Progress indicator
            if (i + 1) % 20 == 0:
                print(f"  Completed {i + 1}/{num_queries} queries...")

        # Calculate final statistics
        results['total_time_ms'] = sum(query_times)
        results['average_time_ms'] = results['total_time_ms'] / len(query_times)
        results['min_time_ms'] = min(query_times)
        results['max_time_ms'] = max(query_times)

        if path_lengths:
            results['average_path_length'] = sum(path_lengths) / len(path_lengths)

        results['cache_stats'] = self.cache.get_stats()

        return results

    def print_benchmark_results(self, results):
        """Print formatted benchmark results"""
        print("\n" + "="*60)
        print("🏆 PERFORMANCE BENCHMARK RESULTS")
        print("="*60)
        print(f"Total Queries: {results['total_queries']}")
        print(f"Successful Queries: {results['successful_queries']}")
        print(f"Failed Queries: {results['failed_queries']}")
        print(f"Success Rate: {results['successful_queries']/results['total_queries']*100:.1f}%")
        print()
        print("⏱️  TIMING METRICS")
        print(f"Average Query Time: {results['average_time_ms']:.2f} ms")
        print(f"Min Query Time: {results['min_time_ms']:.2f} ms")
        print(f"Max Query Time: {results['max_time_ms']:.2f} ms")
        print(f"Total Execution Time: {results['total_time_ms']:.0f} ms")
        print()
        print("🔗 PATH METRICS")
        print(f"Paths Found: {results['paths_found']}")
        print(f"Average Path Length: {results['average_path_length']:.2f} degrees")
        print()
        print("💾 CACHE METRICS")
        cache_stats = results['cache_stats']
        print(f"Cache Size: {cache_stats['size']}")
        print(f"Cache Hit Rate: {cache_stats['hit_rate']*100:.1f}%")
        print("="*60)

    def run_demo(self):
        """Run complete demo with data generation and benchmarks"""
        print("\n🎯 Starting Social Network Pathfinding Engine Demo\n")

        # Generate demo data
        user_ids = self.generate_demo_data(num_users=500, avg_connections=8)

        # Run benchmark
        benchmark_results = self.run_performance_benchmark(user_ids, num_queries=200)

        # Print results
        self.print_benchmark_results(benchmark_results)

        # Show some example paths
        print("\n🛤️  EXAMPLE PATHFINDING QUERIES")
        print("-" * 40)

        for i in range(5):
            start_user = random.choice(user_ids)
            target_user = random.choice(user_ids)

            if start_user != target_user:
                result = self.pathfinder.find_shortest_path(start_user, target_user)

                start_username = self.graph_db.users[start_user]['username']
                target_username = self.graph_db.users[target_user]['username']

                if result.found:
                    path_usernames = [self.graph_db.users[uid]['username'] for uid in result.path]
                    print(f"{start_username} → {target_username}: {' → '.join(path_usernames)} ({result.distance} degrees)")
                else:
                    print(f"{start_username} → {target_username}: No path found")

        print("\n✅ Demo completed successfully!")

        return benchmark_results

def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(description='Social Network Pathfinding Engine')
    parser.add_argument('--demo', action='store_true', help='Run demo with test data')
    parser.add_argument('--api', action='store_true', help='Start API server')
    parser.add_argument('--users', type=int, default=500, help='Number of demo users')
    parser.add_argument('--queries', type=int, default=100, help='Number of benchmark queries')
    parser.add_argument('--port', type=int, default=5000, help='API server port')

    args = parser.parse_args()

    if args.demo:
        # Run demo
        demo = SocialNetworkDemo()
        demo.generate_demo_data(num_users=args.users)
        demo.run_performance_benchmark(demo.graph_db.users.keys(), num_queries=args.queries)

    elif args.api:
        # Start API server
        try:
            from src.api_server import SocialNetworkAPI
            api = SocialNetworkAPI()
            api.run(port=args.port)
        except ImportError:
            print("❌ API server dependencies not available. Install Flask and run: pip install -r requirements.txt")
    else:
        # Default: run demo
        demo = SocialNetworkDemo()
        demo.run_demo()

if __name__ == '__main__':
    main()
