# Mira on Railway: the official image, pinned by version and digest, plus a
# small launcher (railway/start.py). Bump both together; see CHANGELOG.md.
FROM ghcr.io/miracodeai/mira:0.11.1@sha256:cfe31d675d61a2a3fcd873975da4762c1aad703368888dc8f8dba9cb7e2fbac4

# MIRA_INDEX_DIR is scratch space only: with Postgres, indexes, users and
# settings live in the database, and the launcher keeps the one SQLite side
# file (relationship overrides) in Postgres too, so no volume is needed here.
# FORWARDED_ALLOW_IPS lets uvicorn trust Railway's X-Forwarded-Proto, so the
# dashboard session cookie is marked Secure. MALLOC_ARENA_MAX keeps glibc from
# opening one arena per host CPU (Railway shows 32 CPUs to a 1 vCPU service).
ENV MIRA_INDEX_DIR=/app/data/indexes \
    FORWARDED_ALLOW_IPS=* \
    MALLOC_ARENA_MAX=2 \
    PYTHONUNBUFFERED=1

COPY railway/ /app/railway/

ENTRYPOINT ["python", "/app/railway/start.py"]
