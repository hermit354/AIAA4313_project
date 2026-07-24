"""
Utility functions for LLM providers.
"""

import logging
from typing import Any, Dict, Optional
from models import (
    ModelProvider,
    OllamaProvider,
    GeminiProvider,
    OpenAICompatibleProvider,
)
from prompt import (
    MODEL_PROVIDER_MAPPING,
    GEMINI_API_KEY,
    OPENAI_COMPATIBLE_API_KEY,
    OPENAI_COMPATIBLE_BASE_URL,
)

logger = logging.getLogger(__name__)


def extract_json_from_response(response_text: str) -> str:
    """
    Extract JSON content from markdown code blocks.

    Args:
        response_text: Text that may contain JSON wrapped in markdown code blocks

    Returns:
        Text with markdown code block syntax removed
    """

    response_text = response_text.strip()
    if "<think>" in response_text:
        think_start = response_text.find("<think>")
        think_end = response_text.find("</think>")
        if think_start != -1 and think_end != -1:
            response_text = response_text[:think_start] + response_text[think_end + 8 :]

    # Remove leading ```json if present
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    # Remove trailing ``` if present
    if response_text.endswith("```"):
        response_text = response_text[:-3]
    return response_text


def initialize_llm_provider(model_name: str) -> Any:
    """
    Initialize the appropriate LLM provider based on the model name.

    Args:
        model_name: The name of the model to use

    Returns:
        An initialized LLM provider (either OllamaProvider or GeminiProvider)
    """
    # Default to Ollama provider
    provider = OllamaProvider()
    # If using Gemini and API key is available, use Gemini provider
    model_provider = MODEL_PROVIDER_MAPPING.get(model_name, ModelProvider.OLLAMA)
    if model_provider == ModelProvider.GEMINI:
        if not GEMINI_API_KEY:
            logger.warning("⚠️ Gemini API key not found. Falling back to Ollama.")
        else:
            logger.info(f"🔄 Using Google Gemini API provider with model {model_name}")
            provider = GeminiProvider(api_key=GEMINI_API_KEY)
    elif model_provider == ModelProvider.OPENAI_COMPATIBLE:
        if not OPENAI_COMPATIBLE_API_KEY or not OPENAI_COMPATIBLE_BASE_URL:
            logger.warning(
                "⚠️ OpenAI-compatible API config not found. Falling back to Ollama."
            )
        else:
            logger.info(
                f"🔄 Using OpenAI-compatible API provider with model {model_name}"
            )
            provider = OpenAICompatibleProvider(
                api_key=OPENAI_COMPATIBLE_API_KEY,
                base_url=OPENAI_COMPATIBLE_BASE_URL,
            )
    else:
        logger.info(f"🔄 Using Ollama provider with model {model_name}")
    return provider
