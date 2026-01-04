"""
Initial screening module - quick filter to reduce 100+ ideas to ~50.
"""

import asyncio
from typing import Optional

import sys
sys.path.append('..')

from utils.gemini_client import generate_json
from utils.prompts import QUICK_SCREEN_PROMPT
from models import Idea
from config import SCREENING_CONFIG


async def quick_screen_idea(idea: Idea, budget_tier: str) -> dict:
    """
    Perform quick screening on a single idea.

    Args:
        idea: The idea to screen
        budget_tier: Budget tier for context

    Returns:
        Screening result with scores and pass/fail
    """
    prompt = QUICK_SCREEN_PROMPT.format(
        title=idea.title,
        description=idea.description,
        problem_solved=idea.problem_solved,
        target_customer=idea.target_customer,
        revenue_model=idea.revenue_model,
        budget_tier=budget_tier
    )

    result = await generate_json(prompt, temperature=0.3)

    # Extract scores
    feasibility = result.get("feasibility", {}).get("score", 5)
    clarity = result.get("clarity", {}).get("score", 5)
    uniqueness = result.get("uniqueness", {}).get("score", 5)
    demand = result.get("demand", {}).get("score", 5)

    # Determine pass/fail
    passes = (
        feasibility >= SCREENING_CONFIG["min_feasibility_score"] and
        clarity >= SCREENING_CONFIG["min_clarity_score"] and
        uniqueness >= SCREENING_CONFIG["min_uniqueness_score"] and
        demand >= 4  # Minimum demand threshold
    )

    # Also use AI's recommendation
    ai_pass = result.get("pass", True)

    return {
        "idea_id": idea.id,
        "scores": {
            "feasibility": feasibility,
            "clarity": clarity,
            "uniqueness": uniqueness,
            "demand": demand
        },
        "average_score": (feasibility + clarity + uniqueness + demand) / 4,
        "passes_threshold": passes,
        "ai_recommendation": ai_pass,
        "final_pass": passes and ai_pass,
        "rejection_reason": result.get("rejection_reason") if not (passes and ai_pass) else None
    }


async def batch_screen_ideas(
    ideas: list[Idea],
    budget_tier: str,
    max_concurrent: int = 10
) -> tuple[list[Idea], list[dict]]:
    """
    Screen a batch of ideas concurrently.

    Args:
        ideas: List of ideas to screen
        budget_tier: Budget tier for context
        max_concurrent: Maximum concurrent screening calls

    Returns:
        Tuple of (passed_ideas, all_results)
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def limited_screen(idea: Idea) -> dict:
        async with semaphore:
            try:
                result = await quick_screen_idea(idea, budget_tier)
                result["idea"] = idea
                return result
            except Exception as e:
                # On error, give benefit of the doubt
                return {
                    "idea_id": idea.id,
                    "idea": idea,
                    "final_pass": True,
                    "error": str(e),
                    "average_score": 5.0
                }

    tasks = [limited_screen(idea) for idea in ideas]
    results = await asyncio.gather(*tasks)

    # Separate passed and failed
    passed_ideas = []
    all_results = []

    for result in results:
        all_results.append(result)
        if result.get("final_pass", False):
            passed_ideas.append(result["idea"])

    # Sort passed ideas by average score
    passed_ideas_with_scores = [
        (idea, next(r["average_score"] for r in all_results if r["idea_id"] == idea.id))
        for idea in passed_ideas
    ]
    passed_ideas_with_scores.sort(key=lambda x: x[1], reverse=True)
    passed_ideas = [idea for idea, _ in passed_ideas_with_scores]

    return passed_ideas, all_results


async def screen_ideas(
    ideas: list[Idea],
    budget_tier: str,
    target_pass_count: Optional[int] = None,
    progress_callback=None
) -> tuple[list[Idea], dict]:
    """
    Screen all ideas and return those that pass.

    Args:
        ideas: All generated ideas
        budget_tier: Budget tier for context
        target_pass_count: Target number to pass (adjusts threshold if needed)
        progress_callback: Optional callback for progress updates

    Returns:
        Tuple of (passed_ideas, screening_stats)
    """
    if progress_callback:
        await progress_callback("screening", 0, f"Screening {len(ideas)} ideas")

    # Process in batches to show progress
    batch_size = 20
    all_passed = []
    all_results = []

    for i in range(0, len(ideas), batch_size):
        batch = ideas[i:i + batch_size]
        passed, results = await batch_screen_ideas(batch, budget_tier)

        all_passed.extend(passed)
        all_results.extend(results)

        if progress_callback:
            progress = int(((i + len(batch)) / len(ideas)) * 100)
            await progress_callback(
                "screening",
                progress,
                f"Screened {i + len(batch)}/{len(ideas)} ideas, {len(all_passed)} passed"
            )

    # Calculate stats
    stats = {
        "total_screened": len(ideas),
        "passed": len(all_passed),
        "failed": len(ideas) - len(all_passed),
        "pass_rate": round(len(all_passed) / len(ideas) * 100, 1) if ideas else 0,
        "average_score_passed": round(
            sum(r["average_score"] for r in all_results if r.get("final_pass")) /
            len(all_passed) if all_passed else 0, 2
        ),
        "common_rejection_reasons": _get_common_rejections(all_results)
    }

    # If we have a target and didn't meet it, take top N by score anyway
    if target_pass_count and len(all_passed) < target_pass_count:
        # Sort all ideas by screening score
        sorted_results = sorted(
            all_results,
            key=lambda x: x.get("average_score", 0),
            reverse=True
        )
        all_passed = [r["idea"] for r in sorted_results[:target_pass_count]]
        stats["adjusted_to_meet_target"] = True

    return all_passed, stats


def _get_common_rejections(results: list[dict]) -> list[str]:
    """Extract common rejection reasons."""
    reasons = []
    for r in results:
        if not r.get("final_pass") and r.get("rejection_reason"):
            reasons.append(r["rejection_reason"])

    # Simple frequency count
    from collections import Counter
    counter = Counter(reasons)
    return [reason for reason, count in counter.most_common(5)]
