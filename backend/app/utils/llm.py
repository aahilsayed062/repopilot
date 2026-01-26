"""
LLM Service - Handles interactions with OpenAI and Gemini Chat APIs.
"""

import os
from typing import List, Optional, Dict, Any
import backoff
from openai import AsyncOpenAI, OpenAIError
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMService:
    """Interface for Chat LLM (OpenAI or Gemini)."""
    
    def __init__(self):
        self.openai_client = None
        self.gemini_model = None
        self.using_gemini = False
        
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.using_gemini = True
            # Ensure gemini_chat_model has a default if not set, and add 'models/' prefix if missing
            model_name = settings.gemini_chat_model or "gemini-1.5-flash" # Default to gemini-1.5-flash if not specified
            if not model_name.startswith("models/"):
                model_name = f"models/{model_name}"
            self.gemini_model_name = model_name
        elif settings.openai_api_key:
            self.openai_client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url
            )

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
        json_mode: bool = False
    ) -> str:
        """
        Get completion from LLM.
        """
        if not (self.openai_client or self.using_gemini):
            return self._mock_chat(messages)
            
        try:
            if self.using_gemini:
                return await self._call_gemini(messages, temperature, json_mode)
            else:
                return await self._call_openai(messages, temperature, model, json_mode)
            
        except Exception as e:
            logger.error("llm_call_failed", error=str(e))
            # Fallback to mock if API matches "mock" logic or just error
            if "mock" in str(e).lower():
                 return self._mock_chat(messages)
            raise
            
    @backoff.on_exception(backoff.expo, OpenAIError, max_tries=3)
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
        # OpenAI: role=system|user|assistant
        # Gemini: role=user|model, system instructions configured on model init or part of prompt
        
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
        
        # Gemini Python SDK uses ChatSession
        # But we want a stateless-ish call usually, or we can use GenerativeModel.generate_content
        # For chat, best to use start_chat with history, but history excludes the *new* message
        
        # Pop the last user message to send it for generation
        if history and history[-1]["role"] == "user":
            history.pop() # Remove last message to send it as 'message'
        
        gen_config = genai.GenerationConfig(
            temperature=temperature,
        )
        
        if json_mode:
            gen_config.response_mime_type = "application/json"
        
        model_name = self.gemini_model_name
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
            
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction
        )
        
        chat = model.start_chat(history=history)
        
        response = chat.send_message(
            last_user_message,
            generation_config=gen_config,
            safety_settings={
                 HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                 HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                 HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                 HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            }
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
            "Please configure GEMINI_API_KEY (or OPENAI_API_KEY) to get real grounded answers."
        )


# Global instance
llm = LLMService()
