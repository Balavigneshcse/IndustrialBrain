"""Administrative commands.

    python -m server.app.cli create-user --username alice --role admin --display-name "Alice"
    python -m server.app.cli seed-demo                  (development only: the README demo accounts)
    python -m server.app.cli import-legacy              (re-index documents from the old SQLite + uploads)
    python -m server.app.cli recreate-database NAME     (development/test only: empty, migrated database)
"""
import argparse
import asyncio
import getpass
import hashlib
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from .core.config import REPO_ROOT, get_settings
from .db.models import ROLES, Document, User
from .db.session import dispose_engine, get_sessionmaker
from .services.ingest import ingest, stored_path
from .services.users import create_user, password_problem

DEMO_USERS = [
    ("admin", "Administrator", "admin", "Admin@123"),
    ("engineer", "Plant Engineer", "engineer", "Engineer@123"),
]
DB_NAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def _read_password(args) -> str:
    if args.password_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    if os.environ.get("INDUSMIND_NEW_PASSWORD"):
        return os.environ["INDUSMIND_NEW_PASSWORD"]
    first = getpass.getpass("Password: ")
    if first != getpass.getpass("Repeat password: "):
        _fail("passwords do not match")
    return first


async def cmd_create_user(args) -> None:
    password = _read_password(args)
    problem = password_problem(password, args.username)
    if problem:
        _fail(problem)
    async with get_sessionmaker()() as session:
        if (await session.execute(select(User.id).where(User.username == args.username))).first():
            _fail(f"user '{args.username}' already exists")
        await create_user(session, args.username, args.display_name or args.username, args.role, password, args.email)
        await session.commit()
    print(f"Created {args.role} '{args.username}'.")


async def cmd_seed_demo(_args) -> None:
    if get_settings().indusmind_env == "production":
        _fail("demo accounts are not allowed in production; use create-user")
    async with get_sessionmaker()() as session:
        for username, display_name, role, password in DEMO_USERS:
            if (await session.execute(select(User.id).where(User.username == username))).first():
                print(f"Demo user '{username}' already exists.")
                continue
            await create_user(session, username, display_name, role, password)
            print(f"Created demo {role} '{username}'.")
        await session.commit()


async def cmd_import_legacy(args) -> None:
    """Re-index READY documents from the pre-Postgres SQLite database. Skips duplicates by SHA-256."""
    sqlite_path, uploads = Path(args.sqlite), Path(args.uploads)
    if not sqlite_path.is_file():
        _fail(f"{sqlite_path} not found")
    with sqlite3.connect(f"file:{sqlite_path.as_posix()}?mode=ro", uri=True) as legacy:
        rows = legacy.execute(
            "SELECT document_id, original_name, content_type FROM documents WHERE status = 'READY' ORDER BY id"
        ).fetchall()
    async with get_sessionmaker()() as session:
        owner = (await session.execute(select(User).where(User.username == args.as_user))).scalar_one_or_none()
        if owner is None:
            _fail(f"user '{args.as_user}' does not exist (create it first)")
        imported = 0
        for public_id, name, content_type in rows:
            source = uploads / f"{public_id}{Path(name).suffix}"
            if not source.is_file():
                print(f"  skip {name}: file {source.name} missing")
                continue
            data = source.read_bytes()
            sha256 = hashlib.sha256(data).hexdigest()
            if (await session.execute(select(Document.id).where(Document.sha256 == sha256))).first():
                print(f"  skip {name}: already imported")
                continue
            doc = Document(public_id=public_id, original_name=name, content_type=content_type or "",
                           size_bytes=len(data), sha256=sha256, status="processing", uploaded_by_id=owner.id)
            target = stored_path(doc)
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.resolve() != target.resolve():
                shutil.copyfile(source, target)
            session.add(doc)
            await session.flush()
            await ingest(session, doc)
            await session.commit()
            imported += 1
            print(f"  {doc.status:6} {name}")
    print(f"Imported {imported} of {len(rows)} legacy documents.")


async def cmd_recreate_database(args) -> None:
    settings = get_settings()
    if settings.indusmind_env == "production":
        _fail("recreate-database is disabled in production")
    name = args.name
    url = make_url(settings.sqlalchemy_url)
    if not DB_NAME_PATTERN.match(name) or name in {url.database, "postgres", "template0", "template1"}:
        _fail(f"refusing to recreate database '{name}'")
    admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
    await admin.dispose()
    # Alembic runs its own event loop, so migrate from a worker thread.
    await asyncio.to_thread(migrate, url.set(database=name).render_as_string(hide_password=False))
    print(f"Database '{name}' recreated and migrated.")


def migrate(sqlalchemy_url: str | None = None) -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(REPO_ROOT / "server" / "alembic.ini"))
    config.attributes["configure_logger"] = False
    if sqlalchemy_url:
        config.attributes["sqlalchemy_url"] = sqlalchemy_url
    command.upgrade(config, "head")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m server.app.cli", description="IndusMind administration")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-user", help="create a user (password prompted, or via --password-stdin)")
    p.add_argument("--username", required=True)
    p.add_argument("--role", required=True, choices=ROLES)
    p.add_argument("--display-name")
    p.add_argument("--email")
    p.add_argument("--password-stdin", action="store_true", help="read the password from standard input")
    p.set_defaults(handler=cmd_create_user)

    sub.add_parser("seed-demo", help="create the README demo accounts (not in production)").set_defaults(handler=cmd_seed_demo)

    p = sub.add_parser("import-legacy", help="re-index documents from the old SQLite database")
    p.add_argument("--sqlite", default=str(REPO_ROOT / "data" / "indusmind.db"))
    p.add_argument("--uploads", default=str(REPO_ROOT / "data" / "uploads"))
    p.add_argument("--as-user", default="admin", help="owner recorded for the imported documents")
    p.set_defaults(handler=cmd_import_legacy)

    p = sub.add_parser("recreate-database", help="drop, create and migrate a scratch database (not in production)")
    p.add_argument("name")
    p.set_defaults(handler=cmd_recreate_database)

    sub.add_parser("migrate", help="apply database migrations").set_defaults(handler=None)

    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
        return

    async def run() -> None:
        try:
            await args.handler(args)
        finally:
            await dispose_engine()

    asyncio.run(run())


if __name__ == "__main__":
    main()
