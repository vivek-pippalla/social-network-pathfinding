from concurrent.futures import ThreadPoolExecutor

import pytest
from neo4j import Query

from app.core.exceptions import UserNotFoundException
from app.domain.errors import AppError
from app.repositories import graph_repo, user_repo
from app.services.friend_service import FriendService

pytestmark = pytest.mark.integration


def _create_users(driver, *users):
    with driver.session() as session:
        session.execute_write(
            lambda tx: tx.run(
                """
                UNWIND $users AS row
                CREATE (:User {
                    id: row.id, name: row.name, name_lower: toLower(row.name),
                    source: 'app'
                })
                """,
                users=[{"id": user_id, "name": name} for user_id, name in users],
                timeout=5,
            ).consume()
        )


def test_friend_add_is_canonical_idempotent_and_hook_runs_once(clean_graph):
    driver, _ = clean_graph
    _create_users(driver, ("z-user", "Zed"), ("a-user", "Ava"))
    calls = []
    service = FriendService(on_graph_changed=lambda: calls.append("changed"))

    assert service.add_friend(driver, "z-user", "a-user") == {"created": True}
    assert service.add_friend(driver, "a-user", "z-user") == {"created": False}
    assert calls == ["changed"]
    with driver.session() as session:
        rows = list(
            session.run(
                "MATCH (a:User)-[r:CONNECTED]->(b:User) RETURN a.id AS a, b.id AS b"
            )
        )
    assert [dict(row) for row in rows] == [{"a": "a-user", "b": "z-user"}]


def test_fifty_concurrent_adds_leave_one_relationship(clean_graph):
    driver, _ = clean_graph
    _create_users(driver, ("left", "Left"), ("right", "Right"))

    hook_calls = []
    service = FriendService(on_graph_changed=lambda: hook_calls.append("changed"))
    with ThreadPoolExecutor(max_workers=50) as pool:
        outcomes = list(
            pool.map(lambda _: service.add_friend(driver, "left", "right"), range(50))
        )

    assert sum(outcome["created"] for outcome in outcomes) == 1
    assert hook_calls == ["changed"]
    with driver.session() as session:
        summary = session.run(
            """
            MATCH (a:User)-[r:CONNECTED]-(b:User)
            WITH CASE WHEN a.id < b.id THEN a.id ELSE b.id END AS low,
                 CASE WHEN a.id < b.id THEN b.id ELSE a.id END AS high,
                 count(*) AS copies
            RETURN count(*) AS pairs, sum(copies - 1) AS extra
            """
        ).single()
    assert summary["pairs"] == 1
    assert summary["extra"] == 0


def test_remove_is_idempotent_and_calls_hook_only_for_change(clean_graph):
    driver, _ = clean_graph
    _create_users(driver, ("a", "A"), ("b", "B"))
    calls = []
    service = FriendService(on_graph_changed=lambda: calls.append("changed"))
    service.add_friend(driver, "a", "b")

    assert service.remove_friend(driver, "b", "a") == {"removed": True}
    assert service.remove_friend(driver, "a", "b") == {"removed": False}
    assert calls == ["changed", "changed"]


def test_unknown_users_and_self_friend_are_rejected(clean_graph):
    driver, _ = clean_graph
    _create_users(driver, ("a", "A"))
    service = FriendService()

    with pytest.raises(AppError) as self_error:
        service.add_friend(driver, "a", "a")
    assert (self_error.value.code, self_error.value.status) == (
        "CANNOT_FRIEND_SELF",
        400,
    )
    with pytest.raises(UserNotFoundException):
        service.add_friend(driver, "a", "missing")
    with pytest.raises(UserNotFoundException):
        service.remove_friend(driver, "a", "missing")
    with pytest.raises(UserNotFoundException):
        service.list_friends(driver, "missing")


def test_list_mutual_search_and_pagination(clean_graph):
    driver, _ = clean_graph
    _create_users(
        driver,
        ("a", "Ava"),
        ("b", "Ben"),
        ("c", "Cara"),
        ("d", "Dara"),
    )
    service = FriendService()
    for user_id in ("b", "c", "d"):
        service.add_friend(driver, "a", user_id)
    service.add_friend(driver, "b", "c")

    assert [u["id"] for u in service.list_friends(driver, "a", limit=2)] == ["b", "c"]
    assert [u["id"] for u in service.list_friends(driver, "a", offset=2)] == ["d"]
    assert [u["id"] for u in service.mutual_friends(driver, "a", "b")] == ["c"]
    assert [u["id"] for u in user_repo.search_users(driver, "ar")] == ["c", "d"]
    with driver.session() as session:
        plan = (
            session.run(
                Query(
                    """
                EXPLAIN MATCH (u:User)
                WHERE u.name_lower CONTAINS $q
                RETURN u.id AS id
                """,
                    timeout=5,
                ),
                q="ar",
            )
            .consume()
            .plan
        )
    assert "TextIndex" in str(plan) or "IndexContainsScan" in str(plan)


def test_neo4j_allows_self_loop_merge_but_api_service_rejects_it(clean_graph):
    driver, _ = clean_graph
    _create_users(driver, ("loop", "Loop"))
    with driver.session() as session:
        result = session.run(
            """
            MATCH (u:User {id: 'loop'})
            MERGE (u)-[r:CONNECTED]->(u)
            RETURN count(r) AS relationships
            """
        )
        count = result.single()["relationships"]
        created = result.consume().counters.relationships_created
    assert count == 1
    assert created == 1
    with driver.session() as session:
        session.run("MATCH (u:User)-[r:CONNECTED]->(u) DELETE r").consume()


def test_friendship_api_uses_versioned_routes_and_protects_ownership(api_client):
    caller = api_client.post(
        "/api/v1/auth/register",
        json={
            "name": "Caller",
            "email": "caller@example.com",
            "password": "valid-password-caller",
        },
    )
    target = api_client.post(
        "/api/v1/auth/register",
        json={
            "name": "Target",
            "email": "target@example.com",
            "password": "valid-password-target",
        },
    )
    headers = {"Authorization": f"Bearer {caller.json()['access_token']}"}
    target_id = target.json()["access_token"]
    from app.core.security import decode_access_token

    target_id = decode_access_token(target_id)["sub"]

    first = api_client.post(f"/api/v1/friends/{target_id}", headers=headers)
    second = api_client.post(f"/api/v1/friends/{target_id}", headers=headers)
    listing = api_client.get("/api/v1/friends?limit=1&offset=0", headers=headers)
    removed = api_client.delete(f"/api/v1/friends/{target_id}", headers=headers)
    legacy = api_client.post(f"/friends/{target_id}", headers=headers)

    assert (first.status_code, first.json()) == (201, {"created": True})
    assert (second.status_code, second.json()) == (200, {"created": False})
    assert listing.status_code == 200 and len(listing.json()["items"]) == 1
    assert removed.status_code == 200 and removed.json()["removed"] is True
    assert legacy.status_code == 404
    malformed_id = api_client.post("/api/v1/friends/%27", headers=headers)
    assert malformed_id.status_code == 422
    assert malformed_id.json()["error"]["code"] == "VALIDATION_ERROR"
