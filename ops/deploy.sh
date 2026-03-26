#!/usr/bin/env bash
set -euo pipefail

# ── Variables requeridas ────────────────────────────────────────
REQUIRED_VARS="IMAGE_TAG DEPLOY_ENV COMPOSE_PROJECT_NAME"
for var in $REQUIRED_VARS; do
  if [ -z "${!var:-}" ]; then
    echo "ERROR: variable $var no definida" >&2
    exit 1
  fi
done

ENV_FILE=".env.${DEPLOY_ENV}"
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: archivo $ENV_FILE no encontrado" >&2
  exit 1
fi

# ── Login al registry (opcional) ───────────────────────────────
if [ -n "${REGISTRY_USERNAME:-}" ] && [ -n "${REGISTRY_TOKEN:-}" ]; then
  echo "$REGISTRY_TOKEN" | docker login ghcr.io -u "$REGISTRY_USERNAME" --password-stdin
fi

# ── Red Docker ──────────────────────────────────────────────────
NETWORK_NAME="crm-${DEPLOY_ENV}"
docker network inspect "$NETWORK_NAME" >/dev/null 2>&1 || docker network create "$NETWORK_NAME"

# ── Imagen anterior (para rollback) ────────────────────────────
SERVICE_NAME="gateway"
PREVIOUS_IMAGE=$(docker compose -f ops/docker-compose.deploy.yml ps -q "$SERVICE_NAME" 2>/dev/null \
  | xargs -r docker inspect --format='{{.Config.Image}}' 2>/dev/null || echo "")

# ── Pull nueva imagen ──────────────────────────────────────────
export IMAGE_TAG
docker compose --env-file "$ENV_FILE" -f ops/docker-compose.deploy.yml pull

# ── Migraciones Django ──────────────────────────────────────────
echo "Ejecutando migraciones Django..."
docker compose --env-file "$ENV_FILE" -f ops/docker-compose.deploy.yml run --rm "$SERVICE_NAME" \
  python manage.py migrate --noinput

# ── Deploy ──────────────────────────────────────────────────────
docker compose --env-file "$ENV_FILE" -f ops/docker-compose.deploy.yml up -d --remove-orphans

# ── Health check ────────────────────────────────────────────────
echo "Esperando health check..."
RETRIES=30
DELAY=2
for i in $(seq 1 $RETRIES); do
  STATUS=$(docker inspect --format='{{.State.Health.Status}}' \
    "$(docker compose -f ops/docker-compose.deploy.yml ps -q "$SERVICE_NAME")" 2>/dev/null || echo "starting")
  if [ "$STATUS" = "healthy" ]; then
    echo "Servicio saludable despues de $((i * DELAY)) segundos"
    exit 0
  fi
  echo "  intento $i/$RETRIES – estado: $STATUS"
  sleep "$DELAY"
done

# ── Rollback ────────────────────────────────────────────────────
echo "ERROR: health check fallo despues de $((RETRIES * DELAY)) segundos" >&2
if [ -n "$PREVIOUS_IMAGE" ]; then
  echo "Intentando rollback a $PREVIOUS_IMAGE..."
  export IMAGE_TAG="$PREVIOUS_IMAGE"
  docker compose --env-file "$ENV_FILE" -f ops/docker-compose.deploy.yml up -d --remove-orphans
  echo "Rollback ejecutado. Verificar manualmente."
fi
exit 1
