"""
LLM Service - Handles interactions with OpenAI/Groq and Gemini Chat APIs.

Priority Logic:
1. OpenAI/Groq (if OPENAI_API_KEY is set) - Using for chat (fast!)
2. Gemini (if GEMINI_API_KEY is set) - Fallback for chat
3. Mock (if no keys) - Development only

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
    """Interface for Chat LLM (OpenAI/Groq or Gemini).

    Priority: OpenAI/Groq > Gemini > Mock

    This allows using Groq for fast chat while Gemini handles embeddings.
    """

    def __init__(self):
        self.openai_client = None
        self.gemini_model = None
        self.provider = "mock"  # 'openai', 'gemini', or 'mock'

        # Priority: OpenAI/Groq first (for chat), then Gemini, then mock
        if settings.openai_api_key:
            # Disable OS/env proxy inheritance for LLM calls; local proxy env values
            # were causing slow retries and connection failures to Groq.
            openai_http_client = httpx.AsyncClient(
                trust_env=False,
                timeout=httpx.Timeout(connect=8.0, read=90.0, write=20.0, pool=40.0),
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
        elif settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            # Ensure gemini_chat_model has proper format
            model_name = settings.gemini_chat_model or "gemini-2.0-flash"
            if not model_name.startswith("models/"):
                model_name = f"models/{model_name}"
            self.gemini_model_name = model_name
            self.provider = "gemini"
            logger.info("llm_initialized", provider="Gemini", model=model_name)
        else:
            logger.warning(
                "llm_initialized", provider="mock", message="No API key configured"
            )

    def _supports_openai_json_mode(self) -> bool:
        """Return True if the configured OpenAI endpoint supports response_format JSON."""
        base_url = (settings.openai_base_url or "").lower()
        if not base_url:
            return True
        # Groq's API supports JSON mode via response_format
        return "openai.com" in base_url or "groq.com" in base_url

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        model: str = None,
        json_mode: bool = False,
    ) -> str:
        """
        Get completion from LLM.

        Uses priority: OpenAI/Groq > Gemini > Mock
        """
        if self.provider == "mock":
            return self._mock_chat(messages)

        try:
            if self.provider == "openai":
                return await self._call_openai(messages, temperature, model, json_mode)
            elif self.provider == "gemini":
                return await self._call_gemini(messages, temperature, json_mode)
            else:
                return self._mock_chat(messages)

        except Exception as e:
            logger.error("llm_call_failed", error=str(e), provider=self.provider)
            # Try fallback to Gemini if OpenAI/Groq fails
            if self.provider == "openai" and settings.gemini_api_key:
                logger.warning("llm_fallback_to_gemini", reason=str(e))
                try:
                    genai.configure(api_key=settings.gemini_api_key)
                    return await self._call_gemini(messages, temperature, json_mode)
                except Exception as e2:
                    logger.error("gemini_fallback_failed", error=str(e2))
            raise

    @backoff.on_exception(
        backoff.expo,
        RateLimitError,
        max_tries=5,
        max_time=120,
        factor=3,  # Longer waits for rate limits: 3, 9, 27, 81 seconds
    )
    @backoff.on_exception(backoff.expo, OpenAIError, max_tries=2, max_time=12)
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

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
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
            "Please configure OPENAI_API_KEY (Groq) or GEMINI_API_KEY to get real grounded answers."
        )


# Global instance
llm = LLMService()
