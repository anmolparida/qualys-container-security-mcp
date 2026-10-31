"""Which account pays for Sheldon's AI (LLM) tokens.

Set at deploy time with ``LLM_BILLING``:

* ``host`` (default) - every chat uses the app's own Amazon Bedrock access
  (the ECS task role on AWS, or AWS keys/profile locally). The host pays.
* ``user`` - every person supplies their own key at sign-in and their chats are
  billed to them. The UI sends it with each chat request as headers; it is held
  for that request only, never stored or logged:

      X-LLM-Provider: anthropic | bedrock
      X-LLM-Api-Key:  <Anthropic API key, or Amazon Bedrock API key>
      X-LLM-Region:   <AWS region, bedrock only, e.g. us-east-1>
      X-LLM-Model:    <optional model ID override>
"""

from __future__ import annotations

import contextvars
import os
import re
from dataclasses import dataclass
from typing import Mapping, Optional

import anthropic

DEFAULT_BEDROCK_MODEL = "global.anthropic.claude-haiku-5-5"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-5-5"

_REGION_RE = re.compile(r"^[a-z]{2}(-gov)?-[a-z]+-\d$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9._:\-]{1,128}$")


class LlmAuthError(Exception):
    """User-billing mode: the caller's AI key is missing or invalid."""


def billing_mode() -> str:
    mode = os.environ.get("LLM_BILLING", "host").strip().lower()
    if mode not in ("host", "user"):
        raise RuntimeError("LLM_BILLING must be 'host' or 'user'")
    return mode


@dataclass(frozen=True)
class LlmCredentials:
    provider: str            # "anthropic" | "bedrock"
    api_key: str
    region: Optional[str] = None
    model: Optional[str] = None

    def __repr__(self) -> str:  # never leak the key
        return f"LlmCredentials(provider={self.provider!r}, region={self.region!r}, model={self.model!r}, api_key='***')"

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> "LlmCredentials":
        provider = (headers.get("x-llm-provider") or "").strip().lower()
        key = (headers.get("x-llm-api-key") or "").strip()
        region = (headers.get("x-llm-region") or "").strip().lower() or None
        model = (headers.get("x-llm-model") or "").strip() or None
        if provider not in ("anthropic", "bedrock") or not key:
            raise LlmAuthError(
                "This deployment bills AI usage to each user. Add your Anthropic API key "
                "or Amazon Bedrock API key in the sign-in screen."
            )
        if provider == "bedrock":
            region = region or "us-east-1"
            if not _REGION_RE.match(region):
                raise LlmAuthError(f"'{region}' is not a valid AWS region")
        if model and not _MODEL_RE.match(model):
            raise LlmAuthError("Invalid model ID")
        return cls(provider, key, region, model)


# Per-request user credentials (user billing). Set by the middleware in main.py.
current_llm: contextvars.ContextVar[Optional[LlmCredentials]] = contextvars.ContextVar(
    "llm_credentials", default=None
)

_host_client: Optional[anthropic.AnthropicBedrock] = None


def _host() -> anthropic.AnthropicBedrock:
    # Explicit keys are optional: when absent (e.g. ECS task role) the SDK uses
    # the standard AWS credential chain.
    global _host_client
    if _host_client is None:
        _host_client = anthropic.AnthropicBedrock(
            aws_access_key=os.environ.get("AWS_ACCESS_KEY_ID") or None,
            aws_secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY") or None,
            aws_session_token=os.environ.get("AWS_SESSION_TOKEN") or None,
            aws_region=os.environ.get("AWS_REGION", "us-east-1"),
        )
    return _host_client


def client_and_model():
    """Return (client, model_id) for the current request, honouring LLM_BILLING."""
    if billing_mode() == "host":
        return _host(), os.environ.get("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL)

    creds = current_llm.get()
    if creds is None:
        raise LlmAuthError("Add your AI key in the sign-in screen to use Sheldon chat.")
    if creds.provider == "anthropic":
        client = anthropic.Anthropic(api_key=creds.api_key, max_retries=1)
        model = creds.model or os.environ.get("ANTHROPIC_MODEL_ID", DEFAULT_ANTHROPIC_MODEL)
    else:
        # Amazon Bedrock API key on Bedrock's Anthropic-compatible endpoint.
        client = anthropic.Anthropic(
            api_key=creds.api_key,
            base_url=f"https://bedrock-runtime.{creds.region}.amazonaws.com/anthropic",
            max_retries=1,
        )
        model = creds.model or os.environ.get("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL)
    return client, model


def describe_error(exc: Exception) -> str:
    """Short, user-facing reason for an LLM call failure."""
    if isinstance(exc, anthropic.AuthenticationError):
        return "The AI provider rejected your API key."
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "Your AI key doesn't have access to this model (enable model access, or check permissions)."
    if isinstance(exc, anthropic.NotFoundError):
        return "Model not found for this key/region. Check the model ID or region."
    if isinstance(exc, anthropic.RateLimitError):
        return "Your AI account is rate-limited or out of quota."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Couldn't reach the AI provider."
    return str(exc)
