# Deploy and Host Mira on Railway

Mira is a self-hosted, open-source (Apache-2.0) AI code reviewer. It watches pull requests on GitHub, GitLab, Forgejo/Codeberg or Bitbucket Cloud, indexes your repositories for context, and posts a walkthrough plus inline review comments using the LLM you choose. A web dashboard shows repos, reviews, vulnerabilities, rules and settings.

## About Hosting Mira

This template runs the official Mira 0.11.1 image (pinned by digest) with a small launcher, plus Railway PostgreSQL. Users, settings, indexes and review history live in Postgres, so the Mira service needs no volume and the stack fits Railway's Free plan (one volume). The dashboard admin password and the webhook secret are generated on deploy. The only prompt is your LLM API key (OpenRouter by default; any OpenAI-compatible endpoint works through `LLM_BASE_URL`). The dashboard starts before a Git platform is connected: after deploy, log in, then add your GitHub App, GitLab, Forgejo or Bitbucket variables and redeploy.

## Common Use Cases

* Automatic AI review of every new pull or merge request, with a walkthrough and inline comments
* On-demand reviews and questions by mentioning the bot in a PR comment
* Dependency vulnerability tracking and custom review rules across an organisation's repos

## Dependencies for Mira Hosting

* An LLM API key: OpenRouter, or any OpenAI-compatible endpoint (OpenAI, DeepSeek, Groq, a LiteLLM proxy)
* A Git platform: a GitHub App you create, or a GitLab, Forgejo/Codeberg or Bitbucket access token

### Deployment Dependencies

* Mira source and releases: https://github.com/miracodeai/mira
* Mira documentation: https://docs.miracode.ai
* GitHub App setup: https://docs.miracode.ai/github
* Template repository: https://github.com/aalfath/mira-railway-template

### Implementation Details

Services:

* **Mira**: web dashboard and webhook receiver on the public domain, health check `/health` (it also checks the database).
* **Postgres**: Railway PostgreSQL on its own volume, reached over the private network through `DATABASE_URL`.

After deploy:

1. Open the Mira domain and log in as `admin` with the `ADMIN_PASSWORD` value from the Mira service's Variables tab.
2. Connect a Git platform by adding variables to the Mira service, then redeploy:
   * **GitHub**: create a GitHub App with webhook URL `https://YOUR-DOMAIN/github/webhook` and the webhook secret set to `MIRA_WEBHOOK_SECRET`; permissions Pull requests, Contents, Issues and Checks read and write, Metadata read; events Pull request, Pull request review comment, Issue comment and Push. Set `MIRA_GITHUB_APP_ID` and `MIRA_GITHUB_PRIVATE_KEY` (the full PEM), then install the app on your repos.
   * **GitLab**: set `MIRA_GITLAB_TOKEN` (and `MIRA_GITLAB_API_URL` for self-managed); webhook `https://YOUR-DOMAIN/gitlab/webhook` with secret token `MIRA_WEBHOOK_SECRET`.
   * **Forgejo / Codeberg**: set `MIRA_FORGEJO_TOKEN` and `MIRA_FORGEJO_API_URL` (for example `https://codeberg.org/api/v1`); webhook `https://YOUR-DOMAIN/forgejo/webhook` with secret `MIRA_WEBHOOK_SECRET`.
   * **Bitbucket Cloud**: set `MIRA_BITBUCKET_TOKEN`; webhook `https://YOUR-DOMAIN/bitbucket/webhook` with secret `MIRA_WEBHOOK_SECRET`.
3. Pick repos to index in the dashboard and open a pull request.

Models: `MIRA_MODEL` defaults to `anthropic/claude-sonnet-4-6` on OpenRouter. For another endpoint set `LLM_BASE_URL` (for example `https://api.openai.com/v1`) and a model id that endpoint knows. Extra deployment settings can go in `MIRA_CONFIG_YAML` (YAML, same keys as Mira's `mira.yaml`).

Resources: on Railway with a 0.5 GB / 1 vCPU limit, Mira peaked at about 120 MB of RAM while indexing a 400-file repository and reviewing a pull request, so it fits the Free plan. Very large repos need more memory while indexing. Mira's optional Codex CLI and AWS Bedrock backends aren't configured by this template.

Updates: the Mira service builds from the template repository. When we bump the pinned Mira version there, Railway shows an update in your project; read the repository's CHANGELOG.md, then apply it. Postgres data is kept.

## Why Deploy Mira on Railway?

<!-- Recommended: Keep this section as shown below -->
Railway is a singular platform to deploy your infrastructure stack. Railway will host your infrastructure so you don't have to deal with configuration, while allowing you to vertically and horizontally scale it.

By deploying Mira on Railway, you are one step closer to supporting a complete full-stack application with minimal burden. Host your servers, databases, AI agents, and more on Railway.
<!-- End recommended section -->
