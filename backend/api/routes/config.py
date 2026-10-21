"""
api/routes/config.py
Endpoints for dynamically managing and testing the active LLM provider and model configuration.
Supports seamless switching between Groq, OpenAI, Ollama, and vLLM directly from the UI.
"""
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional, Any

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from config.settings import get_settings, reload_settings, Settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/config", tags=["Configuration"])

PRESETS = {
    "groq": {
        "name": "Groq Cloud (Ultra-Fast LPU)",
        "default_base_url": "https://api.groq.com/openai/v1",
        "default_analyzer_model": "qwen/qwen3.8-27b",
        "default_suggestions_model": "qwen/qwen3.8-27b",
        "requires_api_key": True,
        "recommended_models": [
            {"id": "qwen/qwen3.8-27b", "label": "Qwen 3.8 27B (Primary / Recommended)"},
            {"id": "qwen-2.5-32b", "label": "Qwen 2.5 32B (Arabic / English Precision)"},
            {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B Versatile"},
            {"id": "llama-3.1-8b-instant", "label": "Llama 3.1 8B Instant (Ultra-Fast)"},
        ],
    },
    "openai": {
        "name": "OpenAI Cloud",
        "default_base_url": "https://api.openai.com/v1",
        "default_analyzer_model": "gpt-4o-mini",
        "default_suggestions_model": "gpt-4o-mini",
        "requires_api_key": True,
        "recommended_models": [
            {"id": "gpt-4o-mini", "label": "GPT-4o Mini (Cost Efficient & Fast)"},
            {"id": "gpt-4o", "label": "GPT-4o (Flagship Multimodal)"},
            {"id": "gpt-3.5-turbo", "label": "GPT-3.5 Turbo"},
        ],
    },
    "ollama": {
        "name": "Ollama (Local / Private)",
        "default_base_url": "http://localhost:11434/v1",
        "default_analyzer_model": "qwen2.5:7b",
        "default_suggestions_model": "qwen2.5:7b",
        "requires_api_key": False,
        "recommended_models": [
            {"id": "qwen2.5:7b", "label": "Qwen 2.5 7B (Default local Arabic/English)"},
            {"id": "qwen2.5:14b", "label": "Qwen 2.5 14B (High accuracy local)"},
            {"id": "qwen2.5:32b", "label": "Qwen 2.5 32B"},
            {"id": "qwen2.5-vl:7b", "label": "Qwen 2.5 VL 7B (Vision & Language)"},
            {"id": "llama3.2:3b", "label": "Llama 3.2 3B (Lightweight)"},
        ],
    },
    "vllm": {
        "name": "vLLM / Custom Self-Hosted",
        "default_base_url": "http://localhost:8080/v1",
        "default_analyzer_model": "ded-analyzer-model",
        "default_suggestions_model": "ded-suggestions-model",
        "requires_api_key": False,
        "recommended_models": [
            {"id": "ded-analyzer-model", "label": "DED Analyzer Model (Spec default)"},
            {"id": "ded-suggestions-model", "label": "DED Suggestions Model"},
        ],
    },
}


def is_masked_key(val: Optional[str]) -> bool:
    """Check if the provided key string is a masked placeholder rather than a real secret."""
    if not val:
        return False
    s = val.strip()
    return "•" in s or "..." in s or "***" in s or s.startswith("••")


def _mask_api_key(key: Optional[str]) -> str:
    if not key or not key.strip():
        return ""
    stripped = key.strip()
    if len(stripped) <= 8:
        return "••••••••"
    return f"{stripped[:4]}...{stripped[-4:]}"


def _persist_to_env(updates: dict[str, Any]) -> None:
    """Safely update keys in the active backend .env file."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return

    try:
        content = env_path.read_text(encoding="utf-8")
        for key, value in updates.items():
            str_val = str(value) if value is not None else ""
            pattern = rf"^{re.escape(key)}=.*$"
            if re.search(pattern, content, flags=re.MULTILINE):
                content = re.sub(pattern, f"{key}={str_val}", content, flags=re.MULTILINE)
            else:
                content += f"\n{key}={str_val}"
        env_path.write_text(content, encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to persist settings to .env: %s", exc)


class LlmConfigResponse(BaseModel):
    provider: str
    base_url: str
    api_key_set: bool
    api_key_masked: str
    analyzer_model: str
    suggestions_model: str
    timeout_seconds: float
    presets: dict[str, Any]


class LlmConfigRequest(BaseModel):
    provider: str = Field(..., description="groq | openai | ollama | vllm")
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    analyzer_model: Optional[str] = None
    suggestions_model: Optional[str] = None
    timeout_seconds: Optional[float] = None


class LlmTestRequest(BaseModel):
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


class LlmTestResponse(BaseModel):
    success: bool
    latency_ms: Optional[int] = None
    message: str
    reply: Optional[str] = None
    error: Optional[str] = None


@router.get("/llm", response_model=LlmConfigResponse)
async def get_llm_config():
    """Retrieve the current active LLM provider and model configuration."""
    cfg = get_settings()
    active_key = cfg.effective_api_key
    return LlmConfigResponse(
        provider=cfg.llm_provider,
        base_url=cfg.effective_llm_base_url,
        api_key_set=bool(active_key and active_key.strip()),
        api_key_masked=_mask_api_key(active_key),
        analyzer_model=cfg.effective_analyzer_model,
        suggestions_model=cfg.effective_suggestions_model,
        timeout_seconds=cfg.llm_timeout_seconds,
        presets=PRESETS,
    )


@router.post("/llm", response_model=LlmConfigResponse)
async def update_llm_config(req: LlmConfigRequest):
    """
    Update LLM provider and model configuration in real-time.
    Immediately applies changes without requiring server restart.
    """
    cfg = get_settings()
    provider = req.provider.lower().strip()

    updates: dict[str, Any] = {
        "LLM_PROVIDER": provider,
    }

    # If new API key was provided (and isn't the masked placeholder)
    new_api_key = cfg.effective_api_key
    new_groq_key = cfg.groq_api_key
    new_openai_key = cfg.openai_api_key

    if req.api_key is not None:
        clean = req.api_key.strip()
        if clean and not clean.startswith("••") and "..." not in clean:
            clean_key = clean
            new_api_key = clean_key
            updates["LLM_API_KEY"] = clean_key
            if provider == "groq":
                new_groq_key = clean_key
                updates["GROQ_API_KEY"] = clean_key
            elif provider == "openai":
                new_openai_key = clean_key
                updates["OPENAI_API_KEY"] = clean_key
        elif req.api_key.strip() == "":
            new_api_key = None
            updates["LLM_API_KEY"] = ""
            if provider == "groq":
                new_groq_key = None
                updates["GROQ_API_KEY"] = ""
            elif provider == "openai":
                new_openai_key = None
                updates["OPENAI_API_KEY"] = ""

    new_base_url = req.base_url.strip() if req.base_url else None
    if new_base_url:
        updates["LLM_BASE_URL"] = new_base_url

    new_analyzer_model = req.analyzer_model.strip() if req.analyzer_model else None
    if new_analyzer_model:
        updates["LLM_ANALYZER_MODEL"] = new_analyzer_model

    new_suggestions_model = req.suggestions_model.strip() if req.suggestions_model else None
    if new_suggestions_model:
        updates["LLM_SUGGESTIONS_MODEL"] = new_suggestions_model

    new_timeout = req.timeout_seconds if req.timeout_seconds is not None else cfg.llm_timeout_seconds
    if req.timeout_seconds is not None:
        updates["LLM_TIMEOUT_SECONDS"] = str(new_timeout)

    # Persist to disk
    _persist_to_env(updates)

    # Reinitialize settings instance
    current_dict = cfg.model_dump()
    current_dict["llm_provider"] = provider
    current_dict["llm_api_key"] = new_api_key
    current_dict["groq_api_key"] = new_groq_key
    current_dict["openai_api_key"] = new_openai_key
    current_dict["llm_base_url"] = new_base_url
    current_dict["llm_analyzer_model"] = new_analyzer_model
    current_dict["llm_suggestions_model"] = new_suggestions_model
    current_dict["llm_timeout_seconds"] = new_timeout

    updated_settings = Settings(**current_dict)
    reload_settings(updated_settings)

    logger.info("Updated runtime LLM config: provider=%s, model=%s", provider, updated_settings.effective_analyzer_model)

    active_key = updated_settings.effective_api_key
    return LlmConfigResponse(
        provider=updated_settings.llm_provider,
        base_url=updated_settings.effective_llm_base_url,
        api_key_set=bool(active_key and active_key.strip()),
        api_key_masked=_mask_api_key(active_key),
        analyzer_model=updated_settings.effective_analyzer_model,
        suggestions_model=updated_settings.effective_suggestions_model,
        timeout_seconds=updated_settings.llm_timeout_seconds,
        presets=PRESETS,
    )


@router.post("/llm/test", response_model=LlmTestResponse)
async def test_llm_connection(req: LlmTestRequest):
    """
    Test connectivity to the selected LLM provider and model.
    Sends a lightweight completion ping to measure round-trip latency and verify authentication.
    """
    cfg = get_settings()
    provider = (req.provider or cfg.llm_provider or "groq").lower().strip()

    # Determine base URL
    base_url = req.base_url
    if not base_url or not base_url.strip():
        if provider == "groq":
            base_url = "https://api.groq.com/openai/v1"
        elif provider == "openai":
            base_url = "https://api.openai.com/v1"
        elif provider == "ollama":
            base_url = "http://localhost:11434/v1"
        else:
            base_url = cfg.vllm_base_url

    base_url = base_url.rstrip("/")

    # Determine API key
    api_key = req.api_key
    if api_key is None or api_key.startswith("••") or "..." in api_key:
        api_key = cfg.effective_api_key

    # Determine model
    model = req.model
    if not model or not model.strip():
        if provider == "groq":
            model = "qwen/qwen3.8-27b"
        elif provider == "openai":
            model = "gpt-4o-mini"
        elif provider == "ollama":
            model = "qwen2.5:7b"
        else:
            model = cfg.vllm_analyzer_model

    headers = {}
    if api_key and api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    test_payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Respond with the single word: OK"}
        ],
        "max_tokens": 10,
        "temperature": 0.0,
    }

    start_time = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                f"{base_url}/chat/completions",
                json=test_payload,
                headers=headers,
            )
            latency_ms = int((time.monotonic() - start_time) * 1000)

            if res.status_code == 200:
                data = res.json()
                reply = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                return LlmTestResponse(
                    success=True,
                    latency_ms=latency_ms,
                    message=f"Connected successfully to {provider.upper()} ({model})!",
                    reply=reply or "OK",
                )
            else:
                error_detail = res.text
                try:
                    err_json = res.json()
                    if "error" in err_json:
                        error_detail = err_json["error"].get("message", str(err_json["error"]))
                except Exception:
                    pass

                return LlmTestResponse(
                    success=False,
                    latency_ms=latency_ms,
                    message=f"HTTP {res.status_code} from {provider.upper()}",
                    error=error_detail[:300],
                )
    except httpx.ConnectError:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        return LlmTestResponse(
            success=False,
            latency_ms=latency_ms,
            message=f"Connection refused at {base_url}",
            error="Could not connect to service. Ensure the local server (e.g. Ollama) is running or check internet connectivity.",
        )
    except httpx.TimeoutException:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        return LlmTestResponse(
            success=False,
            latency_ms=latency_ms,
            message="Connection timed out",
            error="The request timed out after 10 seconds.",
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        return LlmTestResponse(
            success=False,
            latency_ms=latency_ms,
            message="Test failed",
            error=str(exc),
        )


class ModelsListResponse(BaseModel):
    success: bool
    provider: str
    models: list[dict[str, str]]
    count: int
    message: Optional[str] = None
    error: Optional[str] = None


@router.get("/llm/models", response_model=ModelsListResponse)
async def fetch_provider_models(
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
):
    """
    Dynamically fetch the live list of models directly from the provider's API (Groq, Ollama, OpenAI).
    Ensures newly released or custom pulled models are immediately available without hardcoding.
    """
    cfg = get_settings()
    prov = (provider or cfg.llm_provider or "groq").lower().strip()

    if not base_url or not base_url.strip():
        if prov == "groq":
            base_url = "https://api.groq.com/openai/v1"
        elif prov == "openai":
            base_url = "https://api.openai.com/v1"
        elif prov == "ollama":
            base_url = "http://localhost:11434/v1"
        else:
            base_url = cfg.vllm_base_url
    base_url = base_url.rstrip("/")

    # Resolve api key
    key = api_key
    if key is None or is_masked_key(key):
        if prov == "groq":
            key = cfg.groq_api_key or cfg.effective_api_key
        elif prov == "openai":
            key = cfg.openai_api_key or cfg.effective_api_key
        else:
            key = cfg.effective_api_key

    headers = {}
    if key and key.strip():
        headers["Authorization"] = f"Bearer {key.strip()}"

    # For groq and openai, an API key is required to query /models
    if prov in ("groq", "openai") and not (key and key.strip()):
        fallback = PRESETS.get(prov, {}).get("recommended_models", [])
        return ModelsListResponse(
            success=False,
            provider=prov,
            models=fallback,
            count=len(fallback),
            message="Enter your API Key to fetch live models from cloud provider.",
        )

    # Candidate endpoints to query
    endpoints = [f"{base_url}/models"]
    if prov == "ollama":
        if not base_url.endswith("/v1"):
            endpoints = [f"{base_url}/v1/models", f"{base_url}/api/tags", f"{base_url}/models"]
        else:
            base_root = base_url[:-3].rstrip("/")
            endpoints = [f"{base_url}/models", f"{base_root}/api/tags"]

    last_error = None
    raw_list = []

    async with httpx.AsyncClient(timeout=8.0) as client:
        for ep in endpoints:
            try:
                res = await client.get(ep, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, dict):
                        raw_list = data.get("data") or data.get("models") or []
                    elif isinstance(data, list):
                        raw_list = data
                    if raw_list:
                        break
                else:
                    last_error = f"HTTP {res.status_code} from {ep}"
            except Exception as exc:
                last_error = str(exc)

    if not raw_list:
        fallback = PRESETS.get(prov, {}).get("recommended_models", [])
        return ModelsListResponse(
            success=False,
            provider=prov,
            models=fallback,
            count=len(fallback),
            error=last_error or f"Could not find models from {prov}",
        )

    # Process and filter models
    model_ids = []
    seen = set()
    for item in raw_list:
        if isinstance(item, str):
            mid = item
        elif isinstance(item, dict):
            mid = item.get("id") or item.get("name") or item.get("model")
        else:
            continue

        if not mid or mid in seen:
            continue

        lower_id = mid.lower()
        # Filter out non-chat / specialized moderation models
        if any(ign in lower_id for ign in ["whisper", "prompt-guard", "safeguard", "tts", "embed", "dall-e", "moderation"]):
            continue

        seen.add(mid)
        model_ids.append(mid)

    # Priority sorting: qwen/qwen3.8-27b at top, then other qwen, allam, llama, deepseek, gpt/openai
    def sort_priority(name: str):
        n = name.lower()
        if "qwen3.8-27b" in n or "qwen/qwen3.8-27b" in n:
            return (0, 0, n)
        if "qwen" in n:
            return (0, 1, n)
        if "allam" in n:
            return (1, 0, n)
        if "llama" in n:
            return (2, 0, n)
        if "deepseek" in n:
            return (3, 0, n)
        if "gpt" in n:
            return (4, 0, n)
        return (5, 0, n)

    sorted_ids = sorted(model_ids, key=sort_priority)
    models_data = [{"id": mid, "label": mid} for mid in sorted_ids]

    return ModelsListResponse(
        success=True,
        provider=prov,
        models=models_data,
        count=len(models_data),
        message=f"Successfully fetched {len(models_data)} live models from {prov.upper()}.",
    )
