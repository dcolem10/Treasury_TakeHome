#!/usr/bin/env bash
#
# One-command deploy of Label Check to AWS Lightsail Containers.
#
# Prereqs (one-time):
#   1. Docker Desktop installed and running.
#   2. AWS CLI v2 configured with credentials:  aws configure
#   3. Lightsail container plugin (lightsailctl):
#        macOS:  brew install aws/tap/lightsailctl
#        other:  https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-install-software.html
#
# Usage:
#   export ANTHROPIC_API_KEY=sk-ant-...      # your key, never written to the repo
#   ./deploy/deploy.sh
#
# Re-running this script pushes a new image and redeploys the same service.
# To tear everything down later:
#   aws lightsail delete-container-service --service-name "$SERVICE_NAME" --region "$REGION"
#
set -euo pipefail

# ---- Config (override via env if you like) ----------------------------------
SERVICE_NAME="${SERVICE_NAME:-label-check}"
REGION="${REGION:-us-east-1}"
POWER="${POWER:-nano}"          # nano (~$7/mo) | micro (~$10/mo) | small ...
SCALE="${SCALE:-1}"
IMAGE_LOCAL="${IMAGE_LOCAL:-label-check:latest}"
ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-claude-opus-4-8}"

# Resolve repo root (this script lives in <repo>/deploy/).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENDPOINT_JSON="$ROOT/deploy/public-endpoint.json"

# ---- Preflight checks -------------------------------------------------------
command -v docker >/dev/null     || { echo "ERROR: docker not found. Install Docker Desktop and start it."; exit 1; }
command -v aws >/dev/null        || { echo "ERROR: aws CLI not found. Install AWS CLI v2."; exit 1; }
docker info >/dev/null 2>&1       || { echo "ERROR: Docker daemon not running. Start Docker Desktop."; exit 1; }
aws sts get-caller-identity >/dev/null 2>&1 || { echo "ERROR: AWS credentials not configured. Run: aws configure"; exit 1; }
: "${ANTHROPIC_API_KEY:?ERROR: export ANTHROPIC_API_KEY before running (it is never written to the repo).}"

echo "==> Deploying '$SERVICE_NAME' to Lightsail in $REGION (power=$POWER, scale=$SCALE)"

# ---- 1. Build the image (force amd64 — Lightsail runs x86_64) ----------------
echo "==> Building Docker image ($IMAGE_LOCAL) for linux/amd64 ..."
docker build --platform linux/amd64 -t "$IMAGE_LOCAL" "$ROOT"

# ---- 2. Create the container service if it doesn't exist ---------------------
if aws lightsail get-container-services --service-name "$SERVICE_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "==> Container service '$SERVICE_NAME' already exists; reusing it."
else
  echo "==> Creating container service '$SERVICE_NAME' ..."
  aws lightsail create-container-service \
    --service-name "$SERVICE_NAME" --power "$POWER" --scale "$SCALE" --region "$REGION" >/dev/null
  echo "==> Waiting for the service to become READY (can take a few minutes) ..."
  until [ "$(aws lightsail get-container-services --service-name "$SERVICE_NAME" --region "$REGION" \
            --query 'containerServices[0].state' --output text)" = "READY" ]; do
    printf '.'; sleep 10
  done
  echo
fi

# ---- 3. Push the image; capture the generated image reference ----------------
echo "==> Pushing image to Lightsail ..."
PUSH_OUT="$(aws lightsail push-container-image \
  --service-name "$SERVICE_NAME" --label app --image "$IMAGE_LOCAL" --region "$REGION" 2>&1)"
echo "$PUSH_OUT"
IMAGE_REF="$(printf '%s\n' "$PUSH_OUT" | grep -oE ":${SERVICE_NAME}\.app\.[0-9]+" | tail -1)"
[ -n "$IMAGE_REF" ] || { echo "ERROR: could not parse the pushed image reference."; exit 1; }
echo "==> Image reference: $IMAGE_REF"

# ---- 4. Generate the deployment spec with the key (temp file, NOT in repo) ---
CONTAINERS_JSON="$(mktemp -t containers.XXXXXX.json)"
trap 'rm -f "$CONTAINERS_JSON"' EXIT
cat > "$CONTAINERS_JSON" <<JSON
{
  "app": {
    "image": "$IMAGE_REF",
    "ports": { "8000": "HTTP" },
    "environment": {
      "EXTRACTION_BACKEND": "claude",
      "ANTHROPIC_API_KEY": "$ANTHROPIC_API_KEY",
      "ANTHROPIC_MODEL": "$ANTHROPIC_MODEL"
    }
  }
}
JSON

# ---- 5. Deploy --------------------------------------------------------------
echo "==> Creating deployment ..."
aws lightsail create-container-service-deployment \
  --service-name "$SERVICE_NAME" --region "$REGION" \
  --containers "file://$CONTAINERS_JSON" \
  --public-endpoint "file://$ENDPOINT_JSON" >/dev/null

echo "==> Waiting for the deployment to go ACTIVE and pass health checks ..."
until [ "$(aws lightsail get-container-services --service-name "$SERVICE_NAME" --region "$REGION" \
          --query 'containerServices[0].state' --output text)" = "RUNNING" ]; do
  printf '.'; sleep 15
done
echo

URL="$(aws lightsail get-container-services --service-name "$SERVICE_NAME" --region "$REGION" \
       --query 'containerServices[0].url' --output text)"
echo
echo "============================================================"
echo " LIVE URL:  $URL"
echo " Health:    ${URL}api/health"
echo "============================================================"
