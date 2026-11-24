import time
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

from fastapi import HTTPException, status
import litellm
from litellm.caching.caching import Cache

from app.config import settings

logger = logging.getLogger(__name__)

# Initialize LiteLLM local memory cache if enabled
if settings.LITELLM_CACHE_ENABLED:
    try:
        litellm.cache = Cache(type="local")
        logger.info("LiteLLM local memory cache initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize LiteLLM cache: {e}")
        litellm.cache = None
else:
    litellm.cache = None

litellm.telemetry = False


class LLMService:
    def __init__(self):
        self.cache_enabled = settings.LITELLM_CACHE_ENABLED and (litellm.cache is not None)

    def _normalize_gemini_model(self, model_name: str) -> str:
        m = (model_name or "gemini-2.5-flash").strip()
        if not m.startswith("gemini/"):
            return f"gemini/{m}"
        return m

    def _normalize_openrouter_model(self, model_name: str) -> str:
        m = (model_name or "nvidia/nemotron-3.5-lightning:free").strip()
        if not m.startswith("openrouter/"):
            return f"openrouter/{m}"
        return m

    def get_provider_attempts(self) -> List[Dict[str, Any]]:
        """
        Build dual-provider attempts in strict sequential order:
        Attempt 1: Provider 1 (Google Gemini) - Primary
        Attempt 2: Provider 2 (OpenRouter / NVIDIA Nemotron) - Fallback
        """
        gemini_key = settings.gemini_api_key_val or "mock-gemini-key"
        openrouter_key = settings.openrouter_api_key_val or "mock-openrouter-key"

        gemini_model = self._normalize_gemini_model(settings.GEMINI_MODEL)
        openrouter_model = self._normalize_openrouter_model(settings.OPENROUTER_MODEL)

        return [
            {
                "key_id": "key_1",
                "provider": "gemini",
                "display_provider": "Google Gemini",
                "model": gemini_model,
                "api_key": gemini_key,
            },
            {
                "key_id": "key_2",
                "provider": "openrouter",
                "display_provider": "OpenRouter / NVIDIA Nemotron",
                "model": openrouter_model,
                "api_key": openrouter_key,
            }
        ]

    def sanitize_error(self, err_text: str) -> str:
        """Scrub API keys and sensitive tokens from error messages."""
        if not err_text:
            return ""

        sanitized = err_text
        secret_keys = [
            settings.gemini_api_key_val,
            settings.openrouter_api_key_val,
            settings.GEMINI_API_KEY,
            settings.GOOGLE_API_KEY,
            settings.OPENROUTER_API_KEY,
        ]

        for key in secret_keys:
            if key and len(key) > 6 and key not in ("mock-gemini-key", "mock-openrouter-key", "mock-key-1", "mock-key-2"):
                sanitized = sanitized.replace(key, "[REDACTED_API_KEY]")

        sanitized = re.sub(r'([?&]key=)[^&\s"\']+', r'\1[REDACTED_API_KEY]', sanitized)
        sanitized = re.sub(r'(Bearer\s+)[A-Za-z0-9_\-\.]{8,}', r'\1[REDACTED_API_KEY]', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)[^"\'\s,]+', r'\1[REDACTED]', sanitized, flags=re.IGNORECASE)
        return sanitized

    def parse_simulation_header(self, header_val: Optional[str]) -> Dict[str, int]:
        """
        Parses X-Simulate-Failure.
        Supports key_1=429, key_2=500, *=429, gemini=429, openrouter=500, nvidia=500.
        """
        if not header_val or not settings.ENABLE_FAILURE_SIMULATION:
            return {}

        sim_map = {}
        parts = [p.strip() for p in header_val.split(",") if p.strip()]
        valid_statuses = {400, 401, 403, 404, 408, 429, 500, 502, 503, 504}

        for part in parts:
            if "=" not in part:
                continue
            target, code_str = part.split("=", 1)
            target = target.strip().lower()
            try:
                code = int(code_str.strip())
                if code in valid_statuses:
                    sim_map[target] = code
                else:
                    logger.warning(f"Ignored unsupported simulation status: {code}")
            except ValueError:
                logger.warning(f"Invalid simulation header part: {part}")

        return sim_map

    def check_cache(self, messages: List[Dict[str, str]], model: str) -> Optional[Dict[str, Any]]:
        """Check LiteLLM cache for a matching model and messages sequence."""
        if not self.cache_enabled or not litellm.cache:
            return None

        try:
            cached_data = litellm.cache.get_cache(model=model, messages=messages)
            if cached_data:
                logger.info(f"Cache HIT for model {model}")
                return cached_data
        except Exception as e:
            logger.warning(f"Error checking cache for {model}: {e}")

        return None

    def store_cache(self, messages: List[Dict[str, str]], reply: str, usage: Dict[str, int], model: str, provider: str):
        """Store response in LiteLLM cache with model and provider metadata."""
        if not self.cache_enabled or not litellm.cache:
            return

        try:
            cached_data = {
                "choices": [{"message": {"content": reply}}],
                "usage": usage,
                "model": model,
                "provider": provider,
            }
            litellm.cache.add_cache(cached_data, model=model, messages=messages)
            logger.info(f"Response successfully cached for model {model} (provider={provider})")
        except Exception as e:
            logger.warning(f"Error storing cache: {e}")

    def execute_chat(
        self,
        messages: List[Dict[str, str]],
        simulation_header: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        start_time = time.time()
        attempts = self.get_provider_attempts()

        # Step 1: Check cache first for configured models
        checked_models = set()
        for attempt in attempts:
            model = attempt["model"]
            if model in checked_models:
                continue
            checked_models.add(model)

            cached_result = self.check_cache(messages, model)
            if cached_result:
                latency_ms = max(1, int((time.time() - start_time) * 1000))
                choices = cached_result.get("choices", [])
                reply = ""
                if choices and isinstance(choices, list):
                    msg_obj = choices[0].get("message", {})
                    reply = msg_obj.get("content", "") or ""

                usage = cached_result.get("usage", {})
                cached_provider = cached_result.get("provider") or attempt["provider"]

                metadata = {
                    "resolution_source": "LLM_CACHE",
                    "source": "LLM_CACHE",
                    "provider": cached_provider,
                    "model": model,
                    "latency_ms": latency_ms,
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "key_id": None,
                    "fallback_attempts": 0,
                    "session_id": session_id,
                }
                return reply, metadata

        # Step 2: Live inference with dual-provider sequential failover
        sim_map = self.parse_simulation_header(simulation_header)
        fallback_attempts = 0
        successful_key_id = None
        successful_model = None
        successful_provider = None
        reply = None

        usage_dict = {
            "input_tokens": 0,
            "output_tokens": 0,
        }
        failure_diagnostics = []

        for attempt in attempts:
            key_id = attempt["key_id"]
            secret_key = attempt["api_key"]
            model = attempt["model"]
            provider = attempt["provider"]
            display_name = attempt["display_provider"]

            # Check simulated failure for wildcard, key_id, or provider name
            sim_code = (
                sim_map.get("*")
                or sim_map.get(key_id)
                or sim_map.get(provider.lower())
                or (sim_map.get("nvidia") if provider.lower() == "openrouter" else None)
            )

            if sim_code:
                logger.warning(
                    f"Simulating failure HTTP {sim_code} on {display_name} ({key_id})"
                )
                failure_diagnostics.append(f"{provider}/{key_id}: Simulated HTTP {sim_code}")
                fallback_attempts += 1
                continue

            try:
                masked_key = (
                    f"{secret_key[:4]}...{secret_key[-3:]}"
                    if len(secret_key) > 8
                    else "***"
                )
                logger.info(
                    f"Attempting inference via {display_name} "
                    f"({key_id}, model={model}, key={masked_key})"
                )

                # Reset litellm.api_key to ensure no key cross-contamination between providers
                litellm.api_key = None

                # Execute completion via LiteLLM
                response = litellm.completion(
                    model=model,
                    messages=messages,
                    api_key=secret_key,
                    timeout=30.0,
                    num_retries=0,
                )

                reply = response.choices[0].message.content or ""

                prompt_tokens = 0
                completion_tokens = 0
                if hasattr(response, "usage") and response.usage:
                    prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
                    completion_tokens = getattr(response.usage, "completion_tokens", 0) or 0
                else:
                    prompt_text = " ".join(m.get("content", "") for m in messages)
                    prompt_tokens = max(1, len(prompt_text) // 4)
                    completion_tokens = max(1, len(reply) // 4)

                usage_dict = {
                    "input_tokens": prompt_tokens,
                    "output_tokens": completion_tokens,
                }

                successful_key_id = key_id
                successful_model = model
                successful_provider = provider

                logger.info(
                    f"Inference succeeded on {display_name} ({key_id}, model={model}) "
                    f"after {fallback_attempts} fallback(s)"
                )
                break

            except Exception as e:
                err_type = type(e).__name__
                safe_err = self.sanitize_error(str(e))
                logger.warning(
                    f"Provider call failed on {display_name} ({key_id}, {err_type}): {safe_err}"
                )
                failure_diagnostics.append(f"{provider}/{key_id} [{err_type}]: {safe_err}")
                fallback_attempts += 1

        # Step 3: Check if all providers failed
        if successful_key_id is None or reply is None:
            logger.error(
                f"All configured providers failed. Diagnostics: {' | '.join(failure_diagnostics)}"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="all providers unavailable"
            )

        latency_ms = max(1, int((time.time() - start_time) * 1000))

        # Step 4: Store successful response in cache
        self.store_cache(
            messages=messages,
            reply=reply,
            usage={
                "prompt_tokens": usage_dict["input_tokens"],
                "completion_tokens": usage_dict["output_tokens"],
                "total_tokens": usage_dict["input_tokens"] + usage_dict["output_tokens"],
            },
            model=successful_model,
            provider=successful_provider,
        )

        # Step 5: Construct complete response metadata
        metadata = {
            "resolution_source": "LIVE_INFERENCE",
            "source": "LIVE_INFERENCE",
            "provider": successful_provider,
            "model": successful_model,
            "latency_ms": latency_ms,
            "input_tokens": usage_dict["input_tokens"],
            "output_tokens": usage_dict["output_tokens"],
            "key_id": successful_key_id,
            "fallback_attempts": fallback_attempts,
            "session_id": session_id,
        }

        return reply, metadata


llm_service = LLMService()
