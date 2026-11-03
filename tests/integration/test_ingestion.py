import hashlib
import uuid
from pathlib import Path

import pytest

from app.cli import _create_demo_user
from app.domain.errors import AppError
from app.models.schemas import UserRegister
from app.repositories import account_repo
from app.services.cache_service import CacheService
from app.services.friend_service import FriendService
from app.services.ingestion_service import (
    DATASET_SHA256,
    DatasetError,
    run_ingestion,
)
from app.core.security import hash_password

pytestmark = pytest.mark.integration
DATASET_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "facebook_combined.txt.gz"
)


def _count(driver, query, **parameters):
    with driver.session() as session:
        record = session.execute_read(lambda tx: tx.run(query, **parameters).single())
    return record["count"]


def _create_registered_user(driver, email: str, name: str) -> str:
    request = UserRegister(name=name, email=email, password="integration-long-password")
    user_id = uuid.uuid4().hex
    account_repo.create_account_and_user(
        driver,
        user_id=user_id,
        name=request.name,
        email=str(request.email),
        email_normalized=str(request.email).lower(),
        password_hash=hash_password(request.password),
    )
    return user_id


def test_official_dataset_counts_idempotency_and_rename_survival(clean_graph):
    driver, redis_client = clean_graph
    cache = CacheService(lambda: redis_client)

    first = run_ingestion(driver, cache, DATASET_PATH)
    with driver.session() as session:
        session.execute_write(
            lambda tx: tx.run(
                "MATCH (u:User {id: '0'}) SET u.name = 'Renamed SNAP User', "
                "u.name_lower = 'renamed snap user'"
            ).consume()
        )
    second = run_ingestion(driver, cache, DATASET_PATH)
    renamed_count = _count(
        driver,
        "MATCH (u:User {id: '0'}) RETURN count(u) AS count",
    )
    with driver.session() as session:
        record = session.execute_read(
            lambda tx: tx.run("MATCH (u:User {id: '0'}) RETURN u.name AS name").single()
        )

    assert hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest() == DATASET_SHA256
    assert (first["snap_users"], first["snap_relationships"]) == (4039, 88234)
    assert first["created_users"] == 4039
    assert first["created_relationships"] == 88234
    assert second["created_users"] == second["created_relationships"] == 0
    assert second["changed"] is False
    assert renamed_count == 1
    assert record["name"] == "Renamed SNAP User"


def test_snap_reset_and_ingestion_preserve_registered_users_and_their_friendship(
    clean_graph,
):
    driver, redis_client = clean_graph
    cache = CacheService(lambda: redis_client)
    first_id = _create_registered_user(driver, "first@example.test", "First")
    second_id = _create_registered_user(driver, "second@example.test", "Second")
    FriendService().add_friend(driver, first_id, second_id)

    run_ingestion(driver, cache, DATASET_PATH)
    reset_result = run_ingestion(driver, cache, DATASET_PATH, reset=True)
    registered_count = _count(
        driver,
        "MATCH (u:User) WHERE u.id IN $ids RETURN count(u) AS count",
        ids=[first_id, second_id],
    )
    app_friendship_count = _count(
        driver,
        "MATCH (:User {id: $first})-[:CONNECTED]-(:User {id: $second}) "
        "RETURN count(*) AS count",
        first=first_id,
        second=second_id,
    )

    assert reset_result["deleted_users"] == 4039
    assert registered_count == 2
    assert app_friendship_count == 1
    assert (reset_result["snap_users"], reset_result["snap_relationships"]) == (
        4039,
        88234,
    )


def test_corrupt_dataset_is_rejected_before_database_writes(clean_graph, tmp_path):
    driver, redis_client = clean_graph
    with driver.session() as session:
        session.execute_write(
            lambda tx: tx.run(
                "CREATE (:User {id: 'sentinel', name: 'Sentinel', source: 'app'})"
            ).consume()
        )
    before = _count(driver, "MATCH (u:User) RETURN count(u) AS count")
    corrupted = tmp_path / "corrupted.txt.gz"
    corrupted.write_bytes(DATASET_PATH.read_bytes()[:-1] + b"x")

    with pytest.raises(DatasetError, match="SHA-256"):
        run_ingestion(driver, CacheService(lambda: redis_client), corrupted)

    after = _count(driver, "MATCH (u:User) RETURN count(u) AS count")
    assert after == before == 1


def test_graph_version_changes_on_ingestion_only_when_graph_changes(clean_graph):
    driver, redis_client = clean_graph
    redis_client.set("graph:version", 10)
    cache = CacheService(lambda: redis_client)

    first = run_ingestion(driver, cache, DATASET_PATH)
    version_after_change = int(redis_client.get("graph:version"))
    second = run_ingestion(driver, cache, DATASET_PATH)

    assert first["changed"] is True
    assert version_after_change == 11
    assert second["changed"] is False
    assert int(redis_client.get("graph:version")) == 11


def test_demo_user_is_created_with_requested_snap_friendships(clean_graph):
    driver, redis_client = clean_graph
    cache = CacheService(lambda: redis_client)
    run_ingestion(driver, cache, DATASET_PATH)

    demo = _create_demo_user(
        driver,
        cache,
        name="Demo Account",
        email="demo@example.test",
        password="demo-account-password",
        friend_count=3,
    )

    account = account_repo.get_account_by_email(driver, "demo@example.test")
    friends = _count(
        driver,
        "MATCH (:User {id: $user_id})-[:CONNECTED]-(friend:User) "
        "WHERE friend.source = 'snap' RETURN count(friend) AS count",
        user_id=demo["user_id"],
    )
    assert account["user_id"] == demo["user_id"]
    assert demo["friends"] == friends == 3
