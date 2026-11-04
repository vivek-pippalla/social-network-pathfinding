"""Operator commands for schema setup and safe graph data management."""

import argparse
import getpass
import json
import sys
import uuid

from neo4j import Driver
from neo4j.exceptions import ConstraintError

from app.core.security import hash_password
from app.db.neo4j_db import close_driver, get_driver
from app.db.schema import ensure_schema
from app.domain.errors import AppError, EmailTakenError
from app.models.schemas import UserRegister
from app.repositories import account_repo, ingestion_repo
from app.services.cache_service import CacheService
from app.services.friend_service import FriendService
from app.services.ingestion_service import (
    DEFAULT_DATASET_PATH,
    ensure_dataset_file,
    run_ingestion,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("schema", help="create missing Neo4j constraints and indexes")

    ingest = commands.add_parser("ingest", help="load the verified SNAP edge list")
    ingest.add_argument("--dataset", type=str, default=str(DEFAULT_DATASET_PATH))
    ingest.add_argument("--batch-size", type=int, default=2000)
    ingest.add_argument("--reset", action="store_true")
    ingest.add_argument("--wipe-all", action="store_true")
    ingest.add_argument("--yes-i-am-sure", action="store_true")

    commands.add_parser("reset-cache", help="invalidate all cached path results")
    demo = commands.add_parser(
        "demo-user", help="create a throwaway graph demo account"
    )
    demo.add_argument("--name", default="Demo User")
    demo.add_argument("--email", required=True)
    demo.add_argument("--friends", type=int, default=5)
    return parser


def _confirm_destructive_options(
    *,
    reset: bool,
    wipe_all: bool,
    yes_i_am_sure: bool,
    is_interactive: bool,
    read_confirmation=input,
) -> None:
    if wipe_all and not reset:
        raise ValueError("--wipe-all requires --reset")
    if yes_i_am_sure and not reset:
        raise ValueError("--yes-i-am-sure requires --reset")
    if not reset:
        return
    if yes_i_am_sure:
        return
    if not is_interactive:
        raise ValueError(
            "Reset requires --yes-i-am-sure when no interactive terminal is available."
        )
    expected = "WIPE ALL DATA" if wipe_all else "RESET SNAP DATA"
    actual = read_confirmation(f"Type {expected} to continue: ")
    if actual != expected:
        raise ValueError("Reset confirmation did not match; no data was changed.")


def _create_demo_user(
    driver: Driver,
    cache: CacheService,
    *,
    name: str,
    email: str,
    password: str,
    friend_count: int,
) -> dict:
    if isinstance(friend_count, bool) or not 0 <= friend_count <= 1000:
        raise ValueError("--friends must be between 0 and 1000")
    request = UserRegister(name=name, email=email, password=password)
    friend_ids = ingestion_repo.random_snap_user_ids(driver, friend_count)
    if len(friend_ids) < friend_count:
        raise ValueError("Not enough SNAP users are available for the requested links.")

    user_id = uuid.uuid4().hex
    try:
        account_repo.create_account_and_user(
            driver,
            user_id=user_id,
            name=request.name,
            email=str(request.email).strip(),
            email_normalized=str(request.email).strip().lower(),
            password_hash=hash_password(request.password),
        )
    except ConstraintError as exc:
        if "email" in str(exc).lower():
            raise EmailTakenError() from None
        raise

    cache.bump_version()
    friend_service = FriendService(on_graph_changed=cache.bump_version)
    for friend_id in friend_ids:
        friend_service.add_friend(driver, user_id, friend_id)

    return {"user_id": user_id, "email": str(request.email), "friends": len(friend_ids)}


def _run(args: argparse.Namespace) -> dict | None:
    if args.command == "reset-cache":
        CacheService().bump_version()
        return {"cache": "invalidated"}

    if args.command == "ingest":
        _confirm_destructive_options(
            reset=args.reset,
            wipe_all=args.wipe_all,
            yes_i_am_sure=args.yes_i_am_sure,
            is_interactive=sys.stdin.isatty(),
        )
        dataset_path = ensure_dataset_file(args.dataset)
        driver = get_driver()
        try:
            cache = CacheService()
            return run_ingestion(
                driver,
                cache,
                dataset_path,
                batch_size=args.batch_size,
                reset=args.reset,
                wipe_all=args.wipe_all,
            )
        finally:
            close_driver()

    if args.command == "schema":
        driver = get_driver()
        try:
            ensure_schema(driver)
        finally:
            close_driver()
        return {"schema": "ready"}

    if args.command == "demo-user":
        if not 0 <= args.friends <= 1000:
            raise ValueError("--friends must be between 0 and 1000")
        password = getpass.getpass("Demo account password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise ValueError("Passwords do not match.")
        driver = get_driver()
        try:
            return _create_demo_user(
                driver,
                CacheService(),
                name=args.name,
                email=args.email,
                password=password,
                friend_count=args.friends,
            )
        finally:
            close_driver()

    raise ValueError("Unsupported command.")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        result = _run(args)
    except (AppError, ValueError, OSError, ConstraintError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if result is not None:
        print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
