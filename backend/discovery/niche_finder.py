"""
Niche discovery module for finding promising startup niches when no topic is provided.
"""

from typing import Optional
import sys
sys.path.append('..')

from utils.gemini_client import generate_json
from utils.prompts import NICHE_DISCOVERY_PROMPT
from config import BUDGET_TIERS


async def parse_budget(budget_input: Optional[str]) -> tuple[str, dict]:
    """
    Parse budget input into a tier name and constraints.

    Args:
        budget_input: User-provided budget string (e.g., "$5000", "50k", "bootstrapped")

    Returns:
        Tuple of (tier_name, tier_config)
    """
    if not budget_input:
        return "bootstrapped", BUDGET_TIERS["bootstrapped"]

    budget_lower = budget_input.lower().strip()

    # Check for tier keywords
    tier_keywords = {
        "bootstrapped": ["bootstrap", "nothing", "zero", "0", "free"],
        "minimal": ["minimal", "tiny", "small"],
        "modest": ["modest", "some"],
        "moderate": ["moderate", "decent"],
        "well_funded": ["well funded", "well-funded", "funded", "series a"],
        "venture_scale": ["venture", "unlimited", "series b", "series c"]
    }

    for tier, keywords in tier_keywords.items():
        for keyword in keywords:
            if keyword in budget_lower:
                return tier, BUDGET_TIERS[tier]

    # Try to parse as number
    try:
        # Remove common formatting
        cleaned = budget_lower.replace("$", "").replace(",", "").replace(" ", "")

        # Handle 'k' suffix for thousands
        if cleaned.endswith("k"):
            amount = float(cleaned[:-1]) * 1000
        elif cleaned.endswith("m"):
            amount = float(cleaned[:-1]) * 1000000
        else:
            amount = float(cleaned)

        # Match to tier
        for tier_name, tier_config in BUDGET_TIERS.items():
            min_val, max_val = tier_config["range"]
            if min_val <= amount < max_val:
                return tier_name, tier_config

        # If above all ranges, it's venture scale
        return "venture_scale", BUDGET_TIERS["venture_scale"]

    except ValueError:
        # Default to bootstrapped if can't parse
        return "bootstrapped", BUDGET_TIERS["bootstrapped"]


async def discover_niche(
    budget_tier: str,
    tech_preference: str = "any",
    impact_focus: str = "general"
) -> dict:
    """
    Discover promising startup niches based on current trends and constraints.

    Args:
        budget_tier: The budget tier name
        tech_preference: User's tech preference
        impact_focus: Area of impact focus

    Returns:
        Dictionary with discovered niches and recommendation
    """
    prompt = NICHE_DISCOVERY_PROMPT.format(
        budget_tier=budget_tier,
        tech_preference=tech_preference,
        impact_focus=impact_focus
    )

    result = await generate_json(prompt, temperature=0.8)

    return {
        "niches": result.get("niches", []),
        "recommended_niche": result.get("recommended_niche", ""),
        "recommendation_reason": result.get("recommendation_reason", ""),
        "discovery_method": "ai_trend_analysis"
    }


async def validate_topic(topic: str, budget_tier: str) -> dict:
    """
    Validate a user-provided topic and assess its viability.

    Args:
        topic: User-provided topic/niche
        budget_tier: Budget tier for context

    Returns:
        Validation result with suggestions
    """
    prompt = f"""Evaluate this startup topic/niche for viability:

Topic: {topic}
Budget tier: {budget_tier}

Assess:
1. Is this a valid, specific enough niche to generate ideas?
2. Is there market opportunity in this space?
3. Is it feasible within the budget constraints?
4. Any refinements to make it more specific or promising?

Respond in JSON:
{{
    "is_valid": true/false,
    "specificity_score": 1-10,
    "market_opportunity": "assessment",
    "budget_feasibility": "assessment",
    "refined_topic": "improved version if needed",
    "suggestions": ["suggestion1", "suggestion2"]
}}"""

    result = await generate_json(prompt, temperature=0.5)
    return result


async def get_topic_or_discover(
    topic: Optional[str],
    budget_tier: str,
    budget_config: dict,
    tech_preference: str = "any",
    impact_focus: str = "general"
) -> dict:
    """
    Get the topic to use for idea generation, discovering if needed.

    Args:
        topic: User-provided topic (may be None or empty)
        budget_tier: Budget tier name
        budget_config: Budget tier configuration
        tech_preference: User's tech preference
        impact_focus: Area of impact focus

    Returns:
        Dictionary with final topic and discovery info
    """
    if topic and topic.strip():
        # Validate user's topic
        validation = await validate_topic(topic.strip(), budget_tier)

        if validation.get("is_valid", True):
            return {
                "topic": validation.get("refined_topic", topic.strip()),
                "original_topic": topic.strip(),
                "was_discovered": False,
                "validation": validation
            }
        else:
            # Topic invalid, discover instead
            discovery = await discover_niche(budget_tier, tech_preference, impact_focus)
            return {
                "topic": discovery["recommended_niche"],
                "original_topic": topic.strip(),
                "was_discovered": True,
                "reason": f"Original topic '{topic}' was too broad. Discovered: {discovery['recommended_niche']}",
                "discovery": discovery
            }
    else:
        # No topic provided, discover
        discovery = await discover_niche(budget_tier, tech_preference, impact_focus)
        return {
            "topic": discovery["recommended_niche"],
            "original_topic": None,
            "was_discovered": True,
            "reason": discovery["recommendation_reason"],
            "discovery": discovery
        }
