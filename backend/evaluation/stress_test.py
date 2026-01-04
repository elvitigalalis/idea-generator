"""
Stress Test module - the "99% killer" that finds fundamental flaws.

This is the critical filter that asks: "How could this idea be fundamentally wrong?"
99% of startup ideas have fatal flaws. This module ruthlessly identifies them.
"""

import asyncio
from typing import Optional

import sys
sys.path.append('..')

from utils.gemini_client import generate_json
from utils.prompts import STRESS_TEST_PROMPT
from models import Idea, StressTestResult
from config import STRESS_TEST_CONFIG


def format_idea_for_stress_test(idea: Idea) -> str:
    """Format idea for stress testing."""
    return f"""Title: {idea.title}
Description: {idea.description}
Problem: {idea.problem_solved}
Customer: {idea.target_customer}
Revenue: {idea.revenue_model}
Impact: {idea.social_impact}"""


async def stress_test_idea(idea: Idea, budget_tier: str) -> StressTestResult:
    """
    Perform brutal stress test on an idea to find fundamental flaws.

    This is the "99% killer" - most ideas fail here, and that's good.
    Better to kill bad ideas early than waste months building them.

    Args:
        idea: The idea to stress test
        budget_tier: Budget tier for context

    Returns:
        StressTestResult with flaws, alternatives, and recommendation
    """
    prompt = STRESS_TEST_PROMPT.format(
        idea_details=format_idea_for_stress_test(idea),
        budget_tier=budget_tier
    )

    result = await generate_json(prompt, temperature=0.4)

    # Parse fundamental flaws
    raw_flaws = result.get("fundamental_flaws", [])
    flaws = []
    for flaw in raw_flaws:
        if isinstance(flaw, dict):
            flaws.append(flaw.get("flaw", str(flaw)))
        else:
            flaws.append(str(flaw))

    # Count fatal and major flaws
    fatal_count = result.get("flaw_count_fatal", 0)
    major_count = result.get("flaw_count_major", 0)

    # Parse alternatives
    raw_alternatives = result.get("alternative_approaches", [])
    alternatives = []
    for alt in raw_alternatives:
        if isinstance(alt, dict):
            alternatives.append(alt.get("approach", str(alt)))
        else:
            alternatives.append(str(alt))

    # Get survival assessment
    survival = result.get("survival_assessment", {})
    survives = survival.get("survives_stress_test", False)
    confidence = float(survival.get("confidence", 5))

    # Determine recommendation
    recommendation = result.get("recommendation", "revise")

    # Override recommendation based on fatal flaw count
    kill_threshold = STRESS_TEST_CONFIG["kill_threshold"]
    if fatal_count >= kill_threshold:
        recommendation = "kill"
    elif fatal_count > 0 or major_count >= 3:
        recommendation = "revise"
    elif survives and confidence >= 7:
        recommendation = "proceed"

    # Calculate survival score (inverse of flaw severity)
    survival_score = max(1, 10 - (fatal_count * 3) - (major_count * 1.5))
    survival_score = min(10, max(1, survival_score))

    return StressTestResult(
        fundamental_flaws=flaws[:10],  # Limit to top 10 flaws
        flaw_count=len(flaws),
        alternative_approaches=alternatives[:5],  # Limit to 5 alternatives
        survival_score=round(survival_score, 1),
        recommendation=recommendation
    )


async def batch_stress_test(
    ideas: list[Idea],
    budget_tier: str,
    max_concurrent: int = 5
) -> list[tuple[Idea, StressTestResult]]:
    """
    Stress test multiple ideas in parallel.

    Args:
        ideas: Ideas to stress test
        budget_tier: Budget tier for context
        max_concurrent: Maximum concurrent tests

    Returns:
        List of (idea, stress_test_result) tuples
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def limited_test(idea: Idea) -> tuple[Idea, StressTestResult]:
        async with semaphore:
            try:
                result = await stress_test_idea(idea, budget_tier)
                return (idea, result)
            except Exception as e:
                # On error, give cautious assessment
                return (idea, StressTestResult(
                    fundamental_flaws=[f"Error during stress test: {str(e)}"],
                    flaw_count=1,
                    alternative_approaches=[],
                    survival_score=5.0,
                    recommendation="revise"
                ))

    tasks = [limited_test(idea) for idea in ideas]
    results = await asyncio.gather(*tasks)

    return list(results)


def filter_survivors(
    stress_results: list[tuple[Idea, StressTestResult]]
) -> tuple[list[Idea], list[Idea], list[Idea]]:
    """
    Categorize ideas based on stress test results.

    Args:
        stress_results: List of (idea, stress_test_result) tuples

    Returns:
        Tuple of (proceed_ideas, revise_ideas, killed_ideas)
    """
    proceed = []
    revise = []
    killed = []

    for idea, result in stress_results:
        if result.recommendation == "proceed":
            proceed.append(idea)
        elif result.recommendation == "revise":
            revise.append(idea)
        else:  # kill
            killed.append(idea)

    return proceed, revise, killed


async def find_the_diamonds(
    ideas: list[Idea],
    budget_tier: str,
    target_count: int = 10,
    progress_callback=None
) -> tuple[list[tuple[Idea, StressTestResult]], dict]:
    """
    Find the 1% diamonds among the 99% of ideas.

    This is the main entry point for stress testing.

    Args:
        ideas: All ideas to stress test
        budget_tier: Budget tier for context
        target_count: Target number of ideas to keep
        progress_callback: Optional callback for progress updates

    Returns:
        Tuple of (surviving_ideas_with_results, stats)
    """
    if progress_callback:
        await progress_callback("stress_test", 0, f"Stress testing {len(ideas)} ideas")

    # Process in batches
    batch_size = 10
    all_results = []

    for i in range(0, len(ideas), batch_size):
        batch = ideas[i:i + batch_size]
        results = await batch_stress_test(batch, budget_tier)
        all_results.extend(results)

        if progress_callback:
            progress = int(((i + len(batch)) / len(ideas)) * 100)
            await progress_callback(
                "stress_test",
                progress,
                f"Stress tested {i + len(batch)}/{len(ideas)} ideas"
            )

    # Categorize results
    proceed, revise, killed = filter_survivors(all_results)

    # Calculate stats
    stats = {
        "total_tested": len(ideas),
        "proceed": len(proceed),
        "revise": len(revise),
        "killed": len(killed),
        "survival_rate": round((len(proceed) + len(revise)) / len(ideas) * 100, 1) if ideas else 0,
        "diamond_rate": round(len(proceed) / len(ideas) * 100, 1) if ideas else 0,
        "common_flaws": _extract_common_flaws(all_results)
    }

    # Sort by survival score
    all_results.sort(key=lambda x: x[1].survival_score, reverse=True)

    # If we don't have enough "proceed" ideas, include best "revise" ideas
    survivors = [(i, r) for i, r in all_results if r.recommendation in ["proceed", "revise"]]

    # Take top N
    survivors = survivors[:target_count]

    return survivors, stats


def _extract_common_flaws(results: list[tuple[Idea, StressTestResult]]) -> list[str]:
    """Extract most common fundamental flaws across all ideas."""
    all_flaws = []
    for _, result in results:
        all_flaws.extend(result.fundamental_flaws)

    # Simple frequency analysis (could be improved with semantic clustering)
    from collections import Counter
    counter = Counter(all_flaws)
    return [flaw for flaw, count in counter.most_common(5)]
