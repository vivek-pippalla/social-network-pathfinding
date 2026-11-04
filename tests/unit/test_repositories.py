"""Unit tests for repository data access functions using mocked driver sessions."""

import unittest
from unittest.mock import MagicMock

from app.repositories import account_repo, graph_repo, ingestion_repo, user_repo


class FakeCounters:
    def __init__(
        self,
        nodes_created=0,
        nodes_deleted=0,
        relationships_created=0,
        relationships_deleted=0,
    ):
        self.nodes_created = nodes_created
        self.nodes_deleted = nodes_deleted
        self.relationships_created = relationships_created
        self.relationships_deleted = relationships_deleted


class FakeSummary:
    def __init__(self, counters=None):
        self.counters = counters or FakeCounters()


class FakeResult:
    def __init__(self, data=None, summary=None):
        self._data = data
        self._summary = summary or FakeSummary()

    def single(self):
        if isinstance(self._data, list):
            return self._data[0] if self._data else None
        return self._data

    def consume(self):
        return self._summary

    def __iter__(self):
        if isinstance(self._data, list):
            return iter(self._data)
        return iter([self._data] if self._data else [])


class FakeTx:
    def __init__(self, run_handler=None):
        self.run_handler = run_handler or (lambda q, **p: FakeResult())

    def run(self, query, **params):
        return self.run_handler(query, **params)


class FakeSession:
    def __init__(self, tx):
        self.tx = tx

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def execute_read(self, fn, *args, **kwargs):
        return fn(self.tx, *args, **kwargs)

    def execute_write(self, fn, *args, **kwargs):
        return fn(self.tx, *args, **kwargs)


class FakeDriver:
    def __init__(self, tx):
        self.tx = tx

    def session(self):
        return FakeSession(self.tx)


class TestRepositoriesUnit(unittest.TestCase):
    def test_user_repo_get_by_id_and_own_profile(self):
        record = {"id": "u1", "name": "Alice", "source": "snap"}
        tx = FakeTx(lambda q, **p: FakeResult(record))
        driver = FakeDriver(tx)

        found = user_repo.get_user_by_id(driver, "u1")
        self.assertEqual(found, record)

        empty_tx = FakeTx(lambda q, **p: FakeResult(None))
        not_found = user_repo.get_user_by_id(FakeDriver(empty_tx), "u1")
        self.assertIsNone(not_found)

        own_profile = {
            "id": "u1",
            "name": "Alice",
            "source": "app",
            "email": "a@example.com",
        }
        profile_tx = FakeTx(lambda q, **p: FakeResult(own_profile))
        found_profile = user_repo.get_own_profile(FakeDriver(profile_tx), "u1")
        self.assertEqual(found_profile, own_profile)

    def test_user_repo_exists_update_and_search(self):
        tx = FakeTx(
            lambda q, **p: FakeResult({"id": "u1", "name": "Bob", "source": "snap"})
        )
        driver = FakeDriver(tx)

        self.assertTrue(user_repo.user_exists(driver, "u1"))
        empty_tx = FakeTx(lambda q, **p: FakeResult(None))
        self.assertFalse(user_repo.user_exists(FakeDriver(empty_tx), "unknown"))

        updated = user_repo.update_user(driver, "u1", "Bob")
        self.assertEqual(updated["name"], "Bob")

        search_records = [{"id": "u1", "name": "Alice", "source": "snap"}]
        search_tx = FakeTx(lambda q, **p: FakeResult(search_records))
        results = user_repo.search_users(
            FakeDriver(search_tx), "ali", offset=0, limit=10
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "u1")

    def test_account_repo_create_and_lookups(self):
        account_record = {
            "id": "u1",
            "name": "Alice",
            "source": "app",
            "email": "alice@example.com",
        }
        tx = FakeTx(lambda q, **p: FakeResult(account_record))
        driver = FakeDriver(tx)

        dummy_hash = "hash-value"
        created = account_repo.create_account_and_user(
            driver,
            user_id="u1",
            name="Alice",
            email="alice@example.com",
            email_normalized="alice@example.com",
            password_hash=dummy_hash,
        )
        self.assertEqual(created["email"], "alice@example.com")

        by_email = account_repo.get_account_by_email(driver, "alice@example.com")
        self.assertEqual(by_email["id"], "u1")

        account_repo.update_password_hash(driver, "u1", "new-hash")

    def test_graph_repo_queries(self):
        users_records = [{"id": "u1", "name": "Alice"}, {"id": "u2", "name": "Bob"}]
        users_tx = FakeTx(lambda q, **p: FakeResult(users_records))
        users_map = graph_repo.get_users_by_ids(FakeDriver(users_tx), ["u1", "u2"])
        self.assertEqual(len(users_map), 2)
        self.assertIn("u1", users_map)

        path_records = {
            "path": [{"id": "u1", "name": "Alice"}, {"id": "u2", "name": "Bob"}]
        }
        path_tx = FakeTx(lambda q, **p: FakeResult(path_records))
        path = graph_repo.find_bounded_shortest_path(FakeDriver(path_tx), "u1", "u2", 5)
        self.assertEqual(len(path), 2)

        with self.assertRaises(ValueError):
            graph_repo.find_bounded_shortest_path(FakeDriver(path_tx), "u1", "u2", 0)

        with self.assertRaises(ValueError):
            graph_repo.find_bounded_shortest_path(FakeDriver(path_tx), "u1", "u2", True)

        recs_records = [{"user_id": "u3", "name": "Charlie", "mutual_friends": 2}]
        recs_tx = FakeTx(lambda q, **p: FakeResult(recs_records))
        recs = graph_repo.get_recommendations(FakeDriver(recs_tx), "u1")
        self.assertEqual(len(recs), 1)

    def test_graph_repo_friendship_mutations(self):
        counters = FakeCounters(relationships_created=1, relationships_deleted=1)
        summary = FakeSummary(counters)
        tx = FakeTx(
            lambda q, **p: FakeResult({"low_id": "u1", "high_id": "u2"}, summary)
        )
        driver = FakeDriver(tx)

        exists, changed = graph_repo.add_friendship(driver, "u2", "u1")
        self.assertTrue(exists)
        self.assertTrue(changed)

        exists, changed = graph_repo.remove_friendship(driver, "u1", "u2")
        self.assertTrue(exists)
        self.assertTrue(changed)

    def test_ingestion_repo_operations(self):
        counters = FakeCounters(
            nodes_created=5, nodes_deleted=10, relationships_deleted=20
        )
        summary = FakeSummary(counters)
        tx = FakeTx(lambda q, **p: FakeResult(None, summary))
        driver = FakeDriver(tx)

        del_nodes, del_rels = ingestion_repo.delete_snap_data(driver)
        self.assertEqual(del_nodes, 10)
        self.assertEqual(del_rels, 20)

        del_all_nodes, del_all_rels = ingestion_repo.delete_all_data(driver)
        self.assertEqual(del_all_nodes, 10)

        merged_nodes = ingestion_repo.merge_snap_users(driver, ["1", "2"])
        self.assertEqual(merged_nodes, 5)

        merged_edges = ingestion_repo.merge_snap_edges(driver, [("1", "2")])
        self.assertIsInstance(merged_edges, int)


if __name__ == "__main__":
    unittest.main()
