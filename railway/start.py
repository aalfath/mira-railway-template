#!/usr/bin/env python3
"""Railway launcher for Mira (https://github.com/miracodeai/mira).

What it adds to the official image's `mira serve`:
  * waits for Postgres before Mira imports its database layer (Mira silently
    falls back to an ephemeral SQLite file when Postgres isn't up yet);
  * writes the deployment config (llm.base_url + api key variable) from
    LLM_BASE_URL / LLM_API_KEY, merged with an optional MIRA_CONFIG_YAML;
  * starts the dashboard even before a Git platform is connected (upstream
    exits with "No platform configured"), so a fresh deploy is healthy and the
    deployer can log in, then add GitHub/GitLab/Forgejo/Bitbucket variables;
  * reuses MIRA_WEBHOOK_SECRET for GitLab/Forgejo/Bitbucket when their own
    webhook secret isn't set, and accepts a GitHub PEM pasted with literal \\n;
  * keeps relationship overrides (Mira's one SQLite side file) in Postgres, so
    the stack needs no volume besides Postgres's own.
Never prints secrets. Exits non-zero on any startup failure so Railway's
ON_FAILURE restart policy applies.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import threading
import time

FILES_TABLE = "mira_railway_files"
REL_NAME = "_relationships.db"


def log(msg: str) -> None:
    print(f"[railway-start] {msg}", flush=True)


def env(name: str) -> str:
    return os.environ.get(name, "").strip()


def fail(msg: str) -> None:
    log(f"ERROR: {msg}")
    sys.exit(1)


def is_pg(url: str) -> bool:
    return url.startswith("postgresql://") or url.startswith("postgres://")


# ── environment fix-ups ────────────────────────────────────────────


def prepare_env() -> None:
    os.makedirs(env("MIRA_INDEX_DIR") or "/app/data/indexes", exist_ok=True)

    key = os.environ.get("MIRA_GITHUB_PRIVATE_KEY", "")
    if key and "\\n" in key and "\n" not in key.strip():
        os.environ["MIRA_GITHUB_PRIVATE_KEY"] = key.replace("\\n", "\n")
        log("MIRA_GITHUB_PRIVATE_KEY had literal \\n sequences; converted them to newlines")

    shared = env("MIRA_WEBHOOK_SECRET")
    for token, secret in (
        ("MIRA_GITLAB_TOKEN", "MIRA_GITLAB_WEBHOOK_SECRET"),
        ("MIRA_FORGEJO_TOKEN", "MIRA_FORGEJO_WEBHOOK_SECRET"),
        ("MIRA_BITBUCKET_TOKEN", "MIRA_BITBUCKET_WEBHOOK_SECRET"),
    ):
        if env(token) and not env(secret) and shared:
            os.environ[secret] = shared
            log(f"{secret} not set: using MIRA_WEBHOOK_SECRET")

    if not env("MIRA_DASHBOARD_URL") and env("RAILWAY_PUBLIC_DOMAIN"):
        os.environ["MIRA_DASHBOARD_URL"] = "https://" + env("RAILWAY_PUBLIC_DOMAIN")

    if not env("ADMIN_PASSWORD"):
        log(
            "ADMIN_PASSWORD is empty: Mira will generate one on first start and write it "
            "to MIRA_INDEX_DIR/initial_admin_password (not persisted without a volume)"
        )


def write_config() -> str:
    """Build the deployment-wide mira.yaml and return its path."""
    if env("MIRA_CONFIG"):
        log("MIRA_CONFIG is set; using it as is")
        return env("MIRA_CONFIG")
    import yaml

    data: dict = {"llm": {"base_url": env("LLM_BASE_URL") or "https://openrouter.ai/api/v1"}}
    if env("LLM_API_KEY"):
        data["llm"]["api_key_env"] = "LLM_API_KEY"
    else:
        log(
            "LLM_API_KEY is empty: reviews will fail until you set it "
            "(or OPENROUTER_API_KEY / OPENAI_API_KEY)"
        )
    extra = os.environ.get("MIRA_CONFIG_YAML", "")
    if extra.strip():
        try:
            overlay = yaml.safe_load(extra) or {}
        except yaml.YAMLError as exc:
            fail(f"MIRA_CONFIG_YAML is not valid YAML: {exc}")
        if not isinstance(overlay, dict):
            fail("MIRA_CONFIG_YAML must be a YAML mapping")
        data = deep_merge(data, overlay)
    path = os.path.join(os.path.dirname(env("MIRA_INDEX_DIR") or "/app/data/indexes"), "mira.yaml")
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)
    return path


def deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        out[k] = deep_merge(out[k], v) if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out


# ── Postgres ───────────────────────────────────────────────────────


def pg_connect(url: str, timeout: int = 10):
    import psycopg

    return psycopg.connect(url, autocommit=True, connect_timeout=timeout)


def wait_for_postgres(url: str) -> None:
    deadline = time.monotonic() + int(env("MIRA_DB_WAIT_SECONDS") or 240)
    attempt = 0
    while True:
        attempt += 1
        try:
            conn = pg_connect(url, timeout=5)
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.close()
            if attempt > 1:
                log(f"Postgres is up after {attempt} attempts")
            return
        except Exception as exc:  # noqa: BLE001
            if time.monotonic() > deadline:
                fail(f"Postgres did not answer in time ({type(exc).__name__}); giving up")
            if attempt == 1 or attempt % 10 == 0:
                log(f"waiting for Postgres ({type(exc).__name__})")
            time.sleep(3)


class SideFileStore:
    """Keeps a small SQLite file from MIRA_INDEX_DIR in a Postgres bytea row."""

    def __init__(self, url: str, name: str) -> None:
        self.url = url
        self.name = name
        self.path = os.path.join(env("MIRA_INDEX_DIR") or "/app/data/indexes", name)
        self.lock = threading.Lock()

    def _conn(self):
        conn = pg_connect(self.url)
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS {FILES_TABLE} ("
                "name TEXT PRIMARY KEY, data BYTEA NOT NULL, "
                "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
        return conn

    def restore(self) -> None:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT data FROM {FILES_TABLE} WHERE name = %s", (self.name,))
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except FileNotFoundError:
                pass
        with open(self.path, "wb") as f:
            f.write(bytes(row[0]))
        log(f"restored {self.name} from Postgres ({len(row[0])} bytes)")

    def save(self) -> None:
        with self.lock:
            src = sqlite3.connect(self.path)
            try:
                data = src.serialize()
            finally:
                src.close()
            conn = self._conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO {FILES_TABLE} (name, data, updated_at) VALUES (%s, %s, now()) "
                        "ON CONFLICT (name) DO UPDATE SET data = EXCLUDED.data, updated_at = now()",
                        (self.name, data),
                    )
            finally:
                conn.close()


def persist_relationships(url: str) -> None:
    store = SideFileStore(url, REL_NAME)
    try:
        store.restore()
    except Exception as exc:  # noqa: BLE001
        fail(f"could not restore {REL_NAME} from Postgres: {exc}")

    from mira.index import relationships as rel

    def wrap(name: str) -> None:
        original = getattr(rel.RelationshipStore, name)

        def wrapper(self, *args, **kwargs):
            result = original(self, *args, **kwargs)
            try:
                store.save()
            except Exception as exc:  # noqa: BLE001
                log(f"WARNING: could not save {REL_NAME} to Postgres: {exc}")
            return result

        setattr(rel.RelationshipStore, name, wrapper)

    for method in ("set_override", "delete_override", "add_custom_edge", "delete_custom_edge"):
        wrap(method)


# ── main ───────────────────────────────────────────────────────────


def platform_configured() -> list[str]:
    found = []
    if env("MIRA_GITHUB_APP_ID") and env("MIRA_GITHUB_PRIVATE_KEY") and env("MIRA_WEBHOOK_SECRET"):
        found.append("GitHub")
    if env("MIRA_GITLAB_TOKEN") and env("MIRA_GITLAB_WEBHOOK_SECRET"):
        found.append("GitLab")
    if env("MIRA_FORGEJO_TOKEN") and env("MIRA_FORGEJO_WEBHOOK_SECRET"):
        found.append("Forgejo")
    if env("MIRA_BITBUCKET_TOKEN") and env("MIRA_BITBUCKET_WEBHOOK_SECRET"):
        found.append("Bitbucket")
    return found


def main() -> None:
    prepare_env()
    db_url = env("DATABASE_URL")
    if is_pg(db_url):
        wait_for_postgres(db_url)
        persist_relationships(db_url)
    else:
        log("DATABASE_URL is not Postgres: Mira uses SQLite in MIRA_INDEX_DIR (needs a volume)")

    config_path = write_config()
    port = env("PORT") or "8000"

    platforms = platform_configured()
    if platforms:
        log(f"starting Mira with {', '.join(platforms)} on port {port}")
        from mira.cli import main as mira_main

        sys.argv = ["mira", "serve", "--config", config_path, "--port", port]
        mira_main()  # click exits the process itself
        return

    log(
        "no Git platform is configured yet: starting the dashboard only. Connect GitHub "
        "(MIRA_GITHUB_APP_ID + MIRA_GITHUB_PRIVATE_KEY), GitLab (MIRA_GITLAB_TOKEN), Forgejo "
        "(MIRA_FORGEJO_TOKEN + MIRA_FORGEJO_API_URL) or Bitbucket (MIRA_BITBUCKET_TOKEN), then redeploy"
    )
    import logging

    import uvicorn

    from mira.config import set_global_defaults

    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s", stream=sys.stdout)
    try:
        set_global_defaults(config_path)
    except Exception as exc:  # noqa: BLE001
        fail(f"invalid deployment config: {exc}")
    from mira.platforms.server import create_app

    uvicorn.run(create_app(), host="0.0.0.0", port=int(port))


if __name__ == "__main__":
    main()
