[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template/mira?utm_medium=integration&utm_source=button&utm_campaign=mira)

# Mira on Railway

One-click Railway template for [Mira](https://github.com/miracodeai/mira), the self-hosted, open-source (Apache-2.0) AI code reviewer for GitHub, GitLab, Forgejo/Codeberg and Bitbucket Cloud pull requests, with a web dashboard.

**Version:** Mira 0.11.1, official image `ghcr.io/miracodeai/mira:0.11.1@sha256:cfe31d675d61a2a3fcd873975da4762c1aad703368888dc8f8dba9cb7e2fbac4`.

## What the template deploys

| Service | Source | What it does |
|---|---|---|
| **Mira** | this repo (`Dockerfile`) | Dashboard and webhook receiver on the public domain. Health check `/health` (also checks the database). No volume needed. |
| **Postgres** | Railway PostgreSQL | Users, settings, repo indexes, review history and vulnerabilities, on its own volume. |

The `Dockerfile` is the official image plus `railway/start.py`, a small launcher that:

* waits for Postgres before Mira starts (Mira would otherwise fall back to a throwaway SQLite file);
* writes Mira's deployment config from `LLM_BASE_URL` / `LLM_API_KEY` (plus optional `MIRA_CONFIG_YAML`);
* starts the dashboard before any Git platform is connected (upstream `mira serve` exits with "No platform configured"), so the first deploy is healthy;
* reuses `MIRA_WEBHOOK_SECRET` for GitLab, Forgejo and Bitbucket when their own webhook secret isn't set, and accepts a GitHub PEM pasted with literal `\n`;
* keeps Mira's one SQLite side file (relationship overrides) in Postgres, so the stack uses a single volume and fits Railway's Free plan;
* exits non-zero on any startup failure, so Railway restarts it.

## Variables

| Variable | Default | Notes |
|---|---|---|
| `LLM_API_KEY` | *(you enter it)* | Your LLM key. OpenRouter by default (https://openrouter.ai/keys). |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | Any OpenAI-compatible endpoint (OpenAI, DeepSeek, Groq, LiteLLM...). |
| `MIRA_MODEL` | `anthropic/claude-sonnet-4-6` | Model id as the endpoint names it. |
| `ADMIN_PASSWORD` | generated | Dashboard password for user `admin` (used on first boot only; change it later in the dashboard). |
| `MIRA_WEBHOOK_SECRET` | generated | Webhook secret to paste into your GitHub App or GitLab/Forgejo/Bitbucket webhook. |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Private Postgres connection. |
| `PORT` | `8080` | Port Mira listens on. |

Add these after deploy to connect a Git platform (then redeploy):

* **GitHub:** `MIRA_GITHUB_APP_ID`, `MIRA_GITHUB_PRIVATE_KEY` (full PEM). Webhook URL `https://YOUR-DOMAIN/github/webhook`, secret = `MIRA_WEBHOOK_SECRET`. Permissions: Pull requests, Contents, Issues, Checks read & write; Metadata read. Events: Pull request, Pull request review comment, Issue comment, Push. Guide: https://docs.miracode.ai/github
* **GitLab:** `MIRA_GITLAB_TOKEN` (+ `MIRA_GITLAB_API_URL` for self-managed). Webhook `https://YOUR-DOMAIN/gitlab/webhook`, secret token = `MIRA_WEBHOOK_SECRET`.
* **Forgejo / Codeberg:** `MIRA_FORGEJO_TOKEN`, `MIRA_FORGEJO_API_URL` (e.g. `https://codeberg.org/api/v1`). Webhook `https://YOUR-DOMAIN/forgejo/webhook`, secret = `MIRA_WEBHOOK_SECRET`.
* **Bitbucket Cloud:** `MIRA_BITBUCKET_TOKEN` (+ optional `MIRA_BITBUCKET_WORKSPACE`). Webhook `https://YOUR-DOMAIN/bitbucket/webhook`, secret = `MIRA_WEBHOOK_SECRET`.

All of Mira's own environment variables still work: https://docs.miracode.ai/configuration/environment-variables

## Resources

Mira idles at about 75 MB of RAM and stayed under 0.5 GB while reviewing and indexing in our tests, so it runs on Railway's Free plan (0.5 GB per service, one volume). Very large repositories need more memory while indexing.

## Updates

The Mira service builds from this repository's `main` branch. When we bump the pinned Mira version, Railway shows an update in every project deployed from the template; read [CHANGELOG.md](CHANGELOG.md) (breaking changes first) and apply it when you're ready. Postgres data is kept.

## Local test

`test/llm-stub.py` is a tiny OpenAI-compatible stub used to test reviews without a real LLM key.
