#!/usr/bin/env bash
# Build, push and deploy the Qualys KCS web app + MCP server to AWS ECS Fargate.
#
#   cp deploy/aws/params.example.env deploy/aws/params.env   # fill in
#   deploy/aws/deploy.sh secret    # only if QUALYS_AUTH_MODE=service: store the shared Qualys account
#   deploy/aws/deploy.sh all       # build + push images, then create/update the stack
#
# Sub-commands: secret | build | deploy | all | outputs
# Requires: aws CLI v2, docker (with buildx), git.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/deploy/aws"
PARAMS="${PARAMS_FILE:-$HERE/params.env}"
[[ -f "$PARAMS" ]] || { echo "Missing $PARAMS (copy params.example.env)"; exit 1; }
set -a; # shellcheck disable=SC1090
source <(sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$PARAMS"); set +a

: "${AWS_REGION:?}" "${STACK_NAME:?}"
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
TAG="${IMAGE_TAG:-$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo local)-$(date +%Y%m%d%H%M%S)}"
WEB_REPO="$STACK_NAME/web"
MCP_REPO="$STACK_NAME/mcp"
WEB_IMAGE="$REGISTRY/$WEB_REPO:$TAG"
MCP_IMAGE="$REGISTRY/$MCP_REPO:$TAG"

cmd_secret() {
  : "${QUALYS_SECRET_NAME:?}"
  read -rp  "Qualys gateway URL (e.g. https://gateway.qg2.apps.qualys.com): " q_url
  read -rsp "Qualys API token (leave blank to use username/password instead): " q_token; echo
  local q_user="" q_pass=""
  if [[ -z "$q_token" ]]; then
    read -rp  "Qualys username: " q_user
    read -rsp "Qualys password: " q_pass; echo
  fi
  local payload
  payload="$(python3 -c 'import json,sys; u,t,n,p=sys.argv[1:]; print(json.dumps({k:v for k,v in {"QUALYS_URL":u,"QUALYS_TOKEN":t,"QUALYS_USERNAME":n,"QUALYS_PASSWORD":p}.items() if v}))' "$q_url" "$q_token" "$q_user" "$q_pass")"
  if aws secretsmanager describe-secret --secret-id "$QUALYS_SECRET_NAME" >/dev/null 2>&1; then
    aws secretsmanager put-secret-value --secret-id "$QUALYS_SECRET_NAME" --secret-string "$payload" >/dev/null
    echo "Updated secret $QUALYS_SECRET_NAME"
  else
    aws secretsmanager create-secret --name "$QUALYS_SECRET_NAME" --secret-string "$payload" >/dev/null
    echo "Created secret $QUALYS_SECRET_NAME"
  fi
}

ensure_repo() {
  aws ecr describe-repositories --repository-names "$1" >/dev/null 2>&1 ||
    aws ecr create-repository --repository-name "$1" \
      --image-scanning-configuration scanOnPush=true --image-tag-mutability IMMUTABLE >/dev/null
}

cmd_build() {
  ensure_repo "$WEB_REPO"; ensure_repo "$MCP_REPO"
  aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"
  # Fargate tasks run linux/amd64; build for it explicitly (Apple Silicon safe).
  docker buildx build --platform linux/amd64 -f "$ROOT/deploy/web.Dockerfile" -t "$WEB_IMAGE" --push "$ROOT"
  docker buildx build --platform linux/amd64 -f "$ROOT/deploy/mcp.Dockerfile" -t "$MCP_IMAGE" --push "$ROOT"
  echo "$TAG" > "$HERE/.last-image-tag"
  echo "Pushed $WEB_IMAGE and $MCP_IMAGE"
}

cmd_deploy() {
  local tag="${IMAGE_TAG:-$(cat "$HERE/.last-image-tag" 2>/dev/null || true)}"
  [[ -n "$tag" ]] || { echo "No image tag - run '$0 build' first or set IMAGE_TAG"; exit 1; }
  local mode="${QUALYS_AUTH_MODE:-user}" secret_arn=""
  if [[ "$mode" == "service" ]]; then
    secret_arn="$(aws secretsmanager describe-secret --secret-id "$QUALYS_SECRET_NAME" --query ARN --output text)" ||
      { echo "Secret $QUALYS_SECRET_NAME not found - run '$0 secret' first"; exit 1; }
  fi

  aws cloudformation deploy \
    --stack-name "$STACK_NAME" \
    --template-file "$HERE/cloudformation.yaml" \
    --capabilities CAPABILITY_IAM \
    --no-fail-on-empty-changeset \
    --parameter-overrides \
      VpcId="$VPC_ID" \
      AlbSubnetIds="$ALB_SUBNET_IDS" \
      ServiceSubnetIds="$SERVICE_SUBNET_IDS" \
      AssignPublicIp="${ASSIGN_PUBLIC_IP:-DISABLED}" \
      AlbScheme="${ALB_SCHEME:-internal}" \
      AllowedIngressCidr="${ALLOWED_INGRESS_CIDR:-10.0.0.0/8}" \
      CertificateArn="$CERTIFICATE_ARN" \
      WebImageUri="$REGISTRY/$WEB_REPO:$tag" \
      McpImageUri="$REGISTRY/$MCP_REPO:$tag" \
      QualysAuthMode="$mode" \
      QualysSecretArn="$secret_arn" \
      LlmBilling="${LLM_BILLING:-host}" \
      BedrockModelId="${BEDROCK_MODEL_ID:-global.anthropic.claude-haiku-5-5}" \
      BedrockRegion="${BEDROCK_REGION:-$AWS_REGION}" \
      McpDefaultQualysUrl="${MCP_DEFAULT_QUALYS_URL:-}" \
      OidcIssuer="${OIDC_ISSUER:-}" \
      OidcAuthorizationEndpoint="${OIDC_AUTHORIZATION_ENDPOINT:-}" \
      OidcTokenEndpoint="${OIDC_TOKEN_ENDPOINT:-}" \
      OidcUserInfoEndpoint="${OIDC_USERINFO_ENDPOINT:-}" \
      OidcClientId="${OIDC_CLIENT_ID:-}" \
      OidcClientSecret="${OIDC_CLIENT_SECRET:-}"
  cmd_outputs
}

cmd_outputs() {
  aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' --output table
}

case "${1:-all}" in
  secret)  cmd_secret ;;
  build)   cmd_build ;;
  deploy)  cmd_deploy ;;
  all)     cmd_build; cmd_deploy ;;
  outputs) cmd_outputs ;;
  *) echo "usage: $0 {secret|build|deploy|all|outputs}"; exit 1 ;;
esac
