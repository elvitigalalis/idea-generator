"""
Evaluation orchestrator - coordinates judges, screening, and stress testing.
"""

import asyncio
from typing import Optional

import sys
sys.path.append('..')

from models import Idea, EvaluatedIdea, StressTestResult
from evaluation.judges import evaluate_with_all_judges, calculate_weighted_score
from evaluation.screener import screen_ideas
from evaluation.stress_test import stress_test_idea, find_the_diamonds
from config import GENERATION_CONFIG


async def evaluate_single_idea(
    idea: Idea,
    budget_tier: str,
    include_stress_test: bool = True
) -> EvaluatedIdea:
    """
    Fully evaluate a single idea with all judges and stress test.

    Args:
        idea: The idea to evaluate
        budget_tier: Budget tier for context
        include_stress_test: Whether to include stress test

    Returns:
        EvaluatedIdea with all evaluations
    """
    # Get evaluations from all judges
    evaluations = await evaluate_with_all_judges(idea, budget_tier)

    # Calculate weighted score
    weighted_score = calculate_weighted_score(evaluations)

    # Run stress test if requested
    stress_test = None
    if include_stress_test:
        stress_test = await stress_test_idea(idea, budget_tier)

        # Adjust score based on stress test survival
        if stress_test.recommendation == "kill":
            weighted_score = weighted_score * 0.5  # Heavily penalize
        elif stress_test.recommendation == "revise":
            weighted_score = weighted_score * 0.8  # Moderate penalty

    # Compile feedback for potential refinement
    all_concerns = []
    for eval in evaluations:
        all_concerns.extend(eval.concerns)

    feedback = "; ".join(set(all_concerns)[:5]) if all_concerns else None

    return EvaluatedIdea(
        idea=idea,
        evaluations=evaluations,
        stress_test=stress_test,
        weighted_score=round(weighted_score, 2),
        feedback_for_refinement=feedback
    )


async def evaluate_ideas_batch(
    ideas: list[Idea],
    budget_tier: str,
    include_stress_test: bool = True,
    max_concurrent: int = 3,
    progress_callback=None
) -> list[EvaluatedIdea]:
    """
    Evaluate a batch of ideas with all judges.

    Args:
        ideas: Ideas to evaluate
        budget_tier: Budget tier for context
        include_stress_test: Whether to include stress test
        max_concurrent: Maximum concurrent evaluations
        progress_callback: Optional callback for progress updates

    Returns:
        List of EvaluatedIdea objects
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []

    async def limited_evaluate(idea: Idea, index: int) -> EvaluatedIdea:
        async with semaphore:
            result = await evaluate_single_idea(idea, budget_tier, include_stress_test)

            if progress_callback:
                progress = int(((index + 1) / len(ideas)) * 100)
                await progress_callback(
                    "evaluation",
                    progress,
                    f"Evaluated {index + 1}/{len(ideas)} ideas"
                )

            return result

    tasks = [limited_evaluate(idea, i) for i, idea in enumerate(ideas)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out errors
    evaluated = []
    for result in results:
        if isinstance(result, Exception):
            print(f"Evaluation error: {result}")
        else:
            evaluated.append(result)

    return evaluated


async def full_evaluation_pipeline(
    ideas: list[Idea],
    budget_tier: str,
    progress_callback=None
) -> tuple[list[EvaluatedIdea], dict]:
    """
    Run the complete evaluation pipeline: screen -> stress test -> judge.

    Args:
        ideas: All generated ideas (100+)
        budget_tier: Budget tier for context
        progress_callback: Optional callback for progress updates

    Returns:
        Tuple of (evaluated_ideas, pipeline_stats)
    """
    stats = {
        "total_ideas": len(ideas),
        "phases": {}
    }

    # Phase 1: Quick screening
    if progress_callback:
        await progress_callback("pipeline", 0, "Phase 1: Initial screening")

    screened_ideas, screening_stats = await screen_ideas(
        ideas,
        budget_tier,
        target_pass_count=60,  # Target ~60 ideas after screening
        progress_callback=progress_callback
    )
    stats["phases"]["screening"] = screening_stats
    stats["after_screening"] = len(screened_ideas)

    # Phase 2: Stress testing (the 99% killer)
    if progress_callback:
        await progress_callback("pipeline", 30, "Phase 2: Stress testing (finding diamonds)")

    survivors, stress_stats = await find_the_diamonds(
        screened_ideas,
        budget_tier,
        target_count=30,  # Target ~30 after stress test
        progress_callback=progress_callback
    )
    stats["phases"]["stress_test"] = stress_stats
    stats["after_stress_test"] = len(survivors)

    # Phase 3: Full judge evaluation on survivors
    if progress_callback:
        await progress_callback("pipeline", 60, "Phase 3: Expert panel evaluation")

    # Extract ideas from survivors (already have stress test results)
    survivor_ideas = [idea for idea, _ in survivors]
    stress_test_map = {idea.id: result for idea, result in survivors}

    # Evaluate with judges (skip stress test since we already have it)
    evaluated = await evaluate_ideas_batch(
        survivor_ideas,
        budget_tier,
        include_stress_test=False,  # Already done
        max_concurrent=3,
        progress_callback=progress_callback
    )

    # Attach stress test results
    for eval_idea in evaluated:
        if eval_idea.idea.id in stress_test_map:
            eval_idea.stress_test = stress_test_map[eval_idea.idea.id]

            # Adjust score based on stress test
            if eval_idea.stress_test.recommendation == "kill":
                eval_idea.weighted_score *= 0.5
            elif eval_idea.stress_test.recommendation == "revise":
                eval_idea.weighted_score *= 0.85

    # Sort by weighted score
    evaluated.sort(key=lambda x: x.weighted_score, reverse=True)

    # Assign ranks
    for i, eval_idea in enumerate(evaluated):
        eval_idea.rank = i + 1

    stats["fully_evaluated"] = len(evaluated)
    stats["top_score"] = evaluated[0].weighted_score if evaluated else 0
    stats["average_score"] = (
        sum(e.weighted_score for e in evaluated) / len(evaluated)
        if evaluated else 0
    )

    return evaluated, stats


async def quick_evaluate_for_ranking(
    ideas: list[Idea],
    budget_tier: str
) -> list[EvaluatedIdea]:
    """
    Quick evaluation for ranking purposes (fewer judges, no stress test).
    Used during refinement loop for faster iteration.

    Args:
        ideas: Ideas to evaluate
        budget_tier: Budget tier for context

    Returns:
        List of EvaluatedIdea with basic scores
    """
    # Use only key judges for speed
    key_judges = ["vc", "impact_investor", "market_validator"]

    results = []
    for idea in ideas:
        evaluations = await evaluate_with_all_judges(idea, budget_tier, key_judges)
        score = calculate_weighted_score(evaluations)

        results.append(EvaluatedIdea(
            idea=idea,
            evaluations=evaluations,
            stress_test=None,
            weighted_score=round(score, 2)
        ))

    return results
