# Changelog

## 0.11.1 (2026-11-24)

First release of the template.

* Mira 0.11.1 (`ghcr.io/miracodeai/mira:0.11.1@sha256:cfe31d675d61a2a3fcd873975da4762c1aad703368888dc8f8dba9cb7e2fbac4`) with Railway PostgreSQL.
* Launcher `railway/start.py`: waits for Postgres, writes the LLM config from `LLM_BASE_URL`/`LLM_API_KEY`, starts the dashboard before a Git platform is connected, keeps relationship overrides in Postgres, exits non-zero on startup failures.
* Upstream release notes: https://github.com/miracodeai/mira/releases/tag/v0.11.1
