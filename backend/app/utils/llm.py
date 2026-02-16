"""
LLM Service - Handles interactions with Ollama (primary), OpenAI/Groq, and Gemini.

Priority Logic (Ollama-First):
1. Ollama (if running locally) - Primary, no token limits
2. OpenAI/Groq (if OPENAI_API_KEY is set) - Fallback
3. Gemini (if GEMINI_API_KEY is set) - Fallback
4. Mock (if nothing available) - Development only

Note: Embeddings are handled separately in embeddings.py (uses Gemini)
"""

import os
import asyncio
from typing import List, Optional, Dict, Any
import backoff
from openai import AsyncOpenAI, OpenAIError, RateLimitError
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMService:
    """Interface for Chat LLM (Ollama > OpenAI/Groq > Gemini > Mock).

    Priority: Ollama > OpenAI/Groq > Gemini > Mock

    Uses Ollama as the primary provider for unlimited local inference.
    Falls back to cloud providers if Ollama is unavailable.
    """

    def __init__(self):
        self.openai_client = None
        self.gemini_model = None
        self.provider = "mock"  # 'ollama', 'openai', 'gemini', or 'mock'
        self.ollama_base_url = settings.ollama_base_url

        # Priority 1: Ollama (local, unlimited)
        if self._check_ollama_available():
            self.provider = "ollama"
            logger.info(
                "llm_initialized",
                provider="Ollama",
                model_a=settings.ollama_model_a,
                model_b=settings.ollama_model_b,
            )
        # Priority 2: OpenAI/Groq
        elif settings.openai_api_key:
            openai_http_client = httpx.AsyncClient(
                trust_env=False,
                timeout=httpx.Timeout(connect=8.0, read=40.0, write=20.0, pool=40.0),
            )
            self.openai_client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                http_client=openai_http_client,
                max_retries=1,
            )
            self.provider = "openai"
            provider_name = (
                "Groq"
                if settings.openai_base_url and "groq" in settings.openai_base_url
                else "OpenAI"
            )
            logger.info(
                "llm_initialized",
                provider=provider_name,
                model=settings.openai_chat_model,
            )
        # Priority 3: Gemini
        elif settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            model_name = settings.gemini_chat_model or "gemini-2.0-flash"
            if not model_name.startswith("models/"):
                model_name = f"models/{model_name}"
            self.gemini_model_name = model_name
            self.provider = "gemini"
            logger.info("llm_initialized", provider="Gemini", model=model_name)
        else:
            logger.warning(
                "llm_initialized", provider="mock", message="No API key or Ollama configured"
            )

    def _check_ollama_available(self) -> bool:
        """Check if Ollama is running and has at least one required model."""
        try:
            import httpx as _httpx
            resp = _httpx.get(f"{self.ollama_base_url}/api/tags", timeout=3.0)
            if resp.status_code != 200:
                return False
            # Verify at least one configured model is actually pulled
            available = {m["name"] for m in resp.json().get("models", [])}
            needed = {settings.ollama_model_a, settings.ollama_model_b}
            # Match by base name (tags list may include :latest suffix)
            for model in needed:
                base = model.split(":")[0]
                if any(a == model or a.startswith(base + ":") for a in available):
                    return True
            logger.warning("ollama_no_models", available=list(available), needed=list(needed))
            return False
        except Exception:
            return False

    def _supports_openai_json_mode(self) -> bool:
        """Return True if the configured OpenAI endpoint supports response_format JSON."""
        base_url = (settings.openai_base_url or "").lower()
        if not base_url:
            return True
        return "openai.com" in base_url

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        model: str = None,
        json_mode: bool = False,
        provider_override: Optional[str] = None,
    ) -> str:
        """
        Get completion from LLM.

        Uses priority: Ollama > OpenAI/Groq > Gemini > Mock (or explicit override)
        
        Args:
            provider_override: Force a specific provider ('ollama', 'ollama_b', 'openai', 'gemini')
                              'ollama_b' uses the secondary Ollama model (Agent B / reviewer)
        """
        provider = provider_override or self.provider

        if provider == "mock":
            return self._mock_chat(messages)

        try:
            if provider == "ollama":
                return await self._call_ollama(messages, temperature, model or settings.ollama_model_a, json_mode)
            elif provider == "ollama_b":
                return await self._call_ollama(messages, temperature, model or settings.ollama_model_b, json_mode)
            elif provider == "openai":
                return await self._call_openai(messages, temperature, model, json_mode)
            elif provider == "gemini":
                return await self._call_gemini(messages, temperature, json_mode)
            else:
                return self._mock_chat(messages)

        except Exception as e:
            logger.error("llm_call_failed", error=str(e), provider=provider)
            # Try fallbacks if no explicit override
            if not provider_override:
                # Try Ollama fallback if not already using it
                if provider != "ollama" and provider != "ollama_b" and self._check_ollama_available():
                    logger.warning("llm_fallback_to_ollama", reason=str(e))
                    try:
                        return await self._call_ollama(messages, temperature, settings.ollama_model_a, json_mode)
                    except Exception as e2:
                        logger.error("ollama_fallback_failed", error=str(e2))
                # Try Gemini fallback
                if provider == "openai" and settings.gemini_api_key:
                    logger.warning("llm_fallback_to_gemini", reason=str(e))
                    try:
                        genai.configure(api_key=settings.gemini_api_key)
                        return await self._call_gemini(messages, temperature, json_mode)
                    except Exception as e2:
                        logger.error("gemini_fallback_failed", error=str(e2))
            raise

    async def _call_ollama(self, messages, temperature, model, json_mode):
        """Call local Ollama API."""
        url = f"{self.ollama_base_url}/api/chat"

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }
        if json_mode:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=120.0)) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

    @backoff.on_exception(
        backoff.expo,
        RateLimitError,
        max_tries=2,
        max_time=15,
        factor=2,
    )
    @backoff.on_exception(backoff.expo, OpenAIError, max_tries=1, max_time=8)
    async def _call_openai(self, messages, temperature, model, json_mode):
        model = model or settings.openai_chat_model

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if json_mode:
            if self._supports_openai_json_mode():
                kwargs["response_format"] = {"type": "json_object"}

        response = await self.openai_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    @backoff.on_exception(backoff.expo, Exception, max_tries=2, max_time=10)
    async def _call_gemini(self, messages, temperature, json_mode):
        # Translate OpenAI messages to Gemini history
        system_instruction = None
        history = []
        last_user_message = ""

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_instruction = content
            elif role == "user":
                last_user_message = content
                history.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                history.append({"role": "model", "parts": [content]})

        # Pop the last user message to send it for generation
        if history and history[-1]["role"] == "user":
            history.pop()

        gen_config = genai.GenerationConfig(
            temperature=temperature,
        )

        if json_mode:
            gen_config.response_mime_type = "application/json"

        model_name = getattr(self, "gemini_model_name", "models/gemini-2.0-flash")
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        model = genai.GenerativeModel(
            model_name=model_name, system_instruction=system_instruction
        )

        chat = model.start_chat(history=history)

        # chat.send_message is synchronous -- run in thread to avoid blocking
        response = await asyncio.to_thread(
            chat.send_message,
            last_user_message,
            generation_config=gen_config,
            safety_settings={
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            },
        )

        return response.text

    def _mock_chat(self, messages: List[Dict[str, str]]) -> str:
        """Return a mock response."""
        last_msg = messages[-1]["content"]
        logger.info("using_mock_llm", prompt_preview=last_msg[:50])
        return (
            "**[MOCK LLM RESPONSE]**\n\n"
            "I am running in mock mode. Here is a simulated answer.\n\n"
            "Based on the context provided, the answer is found in the retrieved chunks.\n"
            "Please install Ollama or configure GEMINI_API_KEY to get real grounded answers."
        )


# Global instance
llm = LLMService()
