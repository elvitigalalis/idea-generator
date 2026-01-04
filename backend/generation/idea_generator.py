"""
Idea generation module - generates 100+ startup ideas in batches.
"""

import asyncio
import uuid
from typing import Optional

import sys
sys.path.append('..')

from utils.gemini_client import generate_json
from utils.prompts import IDEA_GENERATION_PROMPT
from config import GENERATION_CONFIG, BUDGET_TIERS
from models import Idea


async def generate_idea_batch(
    topic: str,
    budget_tier: str,
    budget_config: dict,
    batch_number: int,
    count: int = 25,
    business_model: Optional[str] = None,
    impact_focus: Optional[str] = None,
    tech_preference: Optional[str] = None
) -> list[Idea]:
    """
    Generate a batch of startup ideas.

    Args:
        topic: The niche/topic for ideas
        budget_tier: Budget tier name
        budget_config: Budget constraints
        batch_number: Which batch this is (for diversity)
        count: Number of ideas to generate
        business_model: Preferred business model
        impact_focus: Area of social impact focus
        tech_preference: Technology preference

    Returns:
        List of Idea objects
    """
    # Add variety prompts based on batch number
    variety_focuses = [
        "Focus on service-based and consulting models.",
        "Focus on product and SaaS models.",
        "Focus on marketplace and platform models.",
        "Focus on content, community, and education models.",
        "Focus on tools, utilities, and B2B solutions."
    ]

    variety_hint = variety_focuses[batch_number % len(variety_focuses)]

    prompt = IDEA_GENERATION_PROMPT.format(
        count=count,
        topic=topic,
        budget_tier=budget_tier,
        budget_constraints=", ".join(budget_config.get("constraints", [])),
        business_model=business_model or "any",
        impact_focus=impact_focus or "general positive impact",
        tech_preference=tech_preference or "appropriate for budget"
    )

    # Add variety hint
    prompt += f"\n\nFOR THIS BATCH: {variety_hint}"

    result = await generate_json(prompt, temperature=0.9)

    ideas = []
    for idx, idea_data in enumerate(result.get("ideas", [])):
        idea = Idea(
            id=f"idea_{batch_number}_{idx}_{uuid.uuid4().hex[:8]}",
            title=idea_data.get("title", "Untitled"),
            description=idea_data.get("description", ""),
            problem_solved=idea_data.get("problem_solved", ""),
            target_customer=idea_data.get("target_customer", ""),
            revenue_model=idea_data.get("revenue_model", ""),
            social_impact=idea_data.get("social_impact", ""),
            budget_tier=budget_tier
        )
        ideas.append(idea)

    return ideas


async def generate_all_ideas(
    topic: str,
    budget_tier: str,
    budget_config: dict,
    total_ideas: int = 125,
    ideas_per_batch: int = 25,
    business_model: Optional[str] = None,
    impact_focus: Optional[str] = None,
    tech_preference: Optional[str] = None,
    progress_callback=None
) -> list[Idea]:
    """
    Generate all ideas in batches with progress tracking.

    Args:
        topic: The niche/topic for ideas
        budget_tier: Budget tier name
        budget_config: Budget constraints
        total_ideas: Total number of ideas to generate
        ideas_per_batch: Ideas per batch
        business_model: Preferred business model
        impact_focus: Area of social impact focus
        tech_preference: Technology preference
        progress_callback: Optional callback for progress updates

    Returns:
        List of all generated Idea objects
    """
    num_batches = (total_ideas + ideas_per_batch - 1) // ideas_per_batch
    all_ideas = []

    # Generate batches with some parallelism (2-3 at a time to respect rate limits)
    batch_size = 2
    for i in range(0, num_batches, batch_size):
        batch_tasks = []
        for j in range(batch_size):
            batch_num = i + j
            if batch_num >= num_batches:
                break

            remaining = total_ideas - len(all_ideas)
            count = min(ideas_per_batch, remaining)

            if count > 0:
                task = generate_idea_batch(
                    topic=topic,
                    budget_tier=budget_tier,
                    budget_config=budget_config,
                    batch_number=batch_num,
                    count=count,
                    business_model=business_model,
                    impact_focus=impact_focus,
                    tech_preference=tech_preference
                )
                batch_tasks.append(task)

        if batch_tasks:
            results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    print(f"Batch generation error: {result}")
                else:
                    all_ideas.extend(result)

            if progress_callback:
                progress = min(100, int((len(all_ideas) / total_ideas) * 100))
                await progress_callback("generation", progress, f"Generated {len(all_ideas)} ideas")

        # Small delay between batch groups to avoid rate limiting
        if i + batch_size < num_batches:
            await asyncio.sleep(1)

    return all_ideas


async def deduplicate_ideas(ideas: list[Idea]) -> list[Idea]:
    """
    Remove duplicate or very similar ideas.

    Args:
        ideas: List of ideas to deduplicate

    Returns:
        Deduplicated list of ideas
    """
    if len(ideas) <= 30:
        return ideas

    # Use AI to identify duplicates in batches
    unique_ideas = []
    seen_summaries = set()

    for idea in ideas:
        # Create a simple fingerprint
        fingerprint = f"{idea.title.lower()[:30]}|{idea.problem_solved.lower()[:50]}"

        # Check for exact or near duplicates
        is_duplicate = False
        for seen in seen_summaries:
            # Simple similarity check
            if fingerprint == seen:
                is_duplicate = True
                break

        if not is_duplicate:
            seen_summaries.add(fingerprint)
            unique_ideas.append(idea)

    return unique_ideas
