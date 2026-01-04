"""
Centralized Gemini API client with retry logic and error handling.
"""

import os
import asyncio
import json
import re
from typing import Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Initialize client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Default model
DEFAULT_MODEL = "gemini-2.0-flash"


async def generate_content(
    prompt: str,
    temperature: float = 0.7,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    json_mode: bool = False
) -> str:
    """
    Generate content using Gemini with retry logic.

    Args:
        prompt: The prompt to send to Gemini
        temperature: Creativity level (0.0-1.0)
        max_retries: Number of retry attempts
        retry_delay: Delay between retries in seconds
        json_mode: Whether to request JSON output

    Returns:
        Generated text response
    """
    config = types.GenerateContentConfig(
        temperature=temperature,
    )

    if json_mode:
        config.response_mime_type = "application/json"

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=DEFAULT_MODEL,
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
            else:
                raise Exception(f"Gemini API failed after {max_retries} attempts: {str(e)}")


async def generate_json(
    prompt: str,
    temperature: float = 0.3,
    max_retries: int = 3
) -> dict:
    """
    Generate JSON content using Gemini.

    Args:
        prompt: The prompt requesting JSON output
        temperature: Creativity level (lower for consistent JSON)
        max_retries: Number of retry attempts

    Returns:
        Parsed JSON dictionary
    """
    json_prompt = f"""{prompt}

IMPORTANT: Respond ONLY with valid JSON. No markdown, no code blocks, no explanation."""

    response = await generate_content(
        json_prompt,
        temperature=temperature,
        max_retries=max_retries,
        json_mode=True
    )

    # Clean response and parse JSON
    cleaned = response.strip()

    # Remove markdown code blocks if present
    if cleaned.startswith("```"):
        cleaned = re.sub(r'^```(?:json)?\n?', '', cleaned)
        cleaned = re.sub(r'\n?```$', '', cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}|\[[\s\S]*\]', cleaned)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError(f"Could not parse JSON from response: {cleaned[:200]}")


async def generate_batch(
    prompts: list[str],
    temperature: float = 0.7,
    max_concurrent: int = 5
) -> list[str]:
    """
    Generate content for multiple prompts concurrently.

    Args:
        prompts: List of prompts to process
        temperature: Creativity level
        max_concurrent: Maximum concurrent requests

    Returns:
        List of responses in same order as prompts
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def limited_generate(prompt: str) -> str:
        async with semaphore:
            return await generate_content(prompt, temperature=temperature)

    tasks = [limited_generate(p) for p in prompts]
    return await asyncio.gather(*tasks)


def extract_score(text: str, default: float = 5.0) -> float:
    """
    Extract a numerical score from text response.

    Args:
        text: Text containing a score
        default: Default score if extraction fails

    Returns:
        Extracted score as float
    """
    # Look for patterns like "8/10", "Score: 8", "8 out of 10", just "8"
    patterns = [
        r'(\d+(?:\.\d+)?)\s*/\s*10',      # 8/10, 8.5/10
        r'[Ss]core[:\s]+(\d+(?:\.\d+)?)', # Score: 8, score 8.5
        r'(\d+(?:\.\d+)?)\s*out of\s*10', # 8 out of 10
        r'^(\d+(?:\.\d+)?)\b',            # Starts with number
        r'\b(\d+(?:\.\d+)?)\b',           # Any number (fallback)
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            score = float(match.group(1))
            # Ensure score is in valid range
            if 0 <= score <= 10:
                return score

    return default
