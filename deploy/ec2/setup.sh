#!/usr/bin/env bash
# One-time setup of Sheldon on an Amazon Linux 2023 EC2 instance.
# Run on the instance (SSM Session Manager or SSH), from the repo root:
#
#   sudo DOMAIN=kcs.example.com LLM_BILLING=host bash deploy/ec2/setup.sh
#
# Settings (environment variables, all optional):
#   DOMAIN            DNS name pointing at this instance -> real HTTPS certificate.
#                     Unset -> self-signed certificate on the instance IP (browser warning).
#   LLM_BILLING       host (default): this instance's IAM role pays for Bedrock.
#                     user: each teammate enters their own Anthropic/Bedrock API key.
#   QUALYS_AUTH_MODE  user (default): each teammate signs in with their own Qualys URL + token.
#   AWS_REGION        Bedrock region (default: the instance's region).
#   BEDROCK_MODEL_ID  default global.anthropic.claude-haiku-5-5
#
# No AWS keys or Qualys passwords are written anywhere: Bedrock uses the instance
# IAM role, Qualys uses each user's own token entered in the browser.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "==> Installing Docker"
if ! command -v docker >/dev/null; then
  dnf install -y docker git
  systemctl enable --now docker
fi
if ! docker compose version >/dev/null 2>&1; then
  mkdir -p /usr/local/lib/docker/cli-plugins
  curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

# Instance metadata (IMDSv2) for region / public IP
TOKEN=$(curl -fsS -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 300" || true)
md() { curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/meta-data/$1" 2>/dev/null || true; }
REGION="${AWS_REGION:-$(md placement/region)}"
PUBLIC_IP="$(md public-ipv4)"; PRIVATE_IP="$(md local-ipv4)"

echo "==> Writing .env (no secrets)"
if [[ -f .env ]]; then cp .env ".env.bak.$(date +%s)"; fi
cat > .env <<ENV
QUALYS_AUTH_MODE=${QUALYS_AUTH_MODE:-user}
LLM_BILLING=${LLM_BILLING:-host}
AWS_REGION=${REGION:-us-east-1}
BEDROCK_MODEL_ID=${BEDROCK_MODEL_ID:-global.anthropic.claude-haiku-5-5}
CORS_ORIGINS=
ENV

if [[ -n "${DOMAIN:-}" ]]; then
  export SITE_ADDRESS="$DOMAIN" TLS_DIRECTIVE=""
  URL="https://$DOMAIN"
else
  HOST="${PUBLIC_IP:-$PRIVATE_IP}"
  export SITE_ADDRESS="https://$HOST" TLS_DIRECTIVE="tls internal"
  URL="https://$HOST  (self-signed: click through the browser warning)"
fi
printf 'SITE_ADDRESS=%s\nTLS_DIRECTIVE=%s\n' "$SITE_ADDRESS" "$TLS_DIRECTIVE" >> .env

echo "==> Building and starting (first build takes a few minutes)"
docker compose -f docker-compose.yml -f deploy/ec2/docker-compose.ec2.yml up -d --build

echo
echo "Sheldon is starting at: $URL"
echo "MCP endpoint:           ${URL%% *}/mcp"
echo "Logs:   docker compose logs -f web"
echo "Update: git pull && docker compose -f docker-compose.yml -f deploy/ec2/docker-compose.ec2.yml up -d --build"
echo "Stop:   docker compose -f docker-compose.yml -f deploy/ec2/docker-compose.ec2.yml down"
