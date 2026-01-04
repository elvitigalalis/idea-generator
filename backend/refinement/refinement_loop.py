"""
Refinement Loop module - iteratively improves top ideas until convergence.

The loop continues until:
1. Maximum iterations reached (default: 3)
2. Score improvement < threshold (convergence)
3. Quality threshold met (score > 8.0)
"""

import asyncio
from typing import Optional

import sys
sys.path.append('..')

from models import Idea, EvaluatedIdea, RefinedIdea
from generation.idea_refiner import refine_idea, batch_refine_ideas
from evaluation.evaluator import evaluate_single_idea, quick_evaluate_for_ranking
from ranking.ranker import rank_ideas, calculate_final_score
from config import GENERATION_CONFIG


async def run_refinement_iteration(
    evaluated_ideas: list[EvaluatedIdea],
    budget_tier: str,
    iteration: int,
    progress_callback=None
) -> list[EvaluatedIdea]:
    """
    Run a single refinement iteration on top ideas.

    Args:
        evaluated_ideas: Ideas to refine
        budget_tier: Budget tier for context
        iteration: Current iteration number
        progress_callback: Optional callback for progress updates

    Returns:
        List of newly evaluated refined ideas
    """
    if progress_callback:
        await progress_callback(
            "refinement",
            0,
            f"Refinement iteration {iteration}: Refining {len(evaluated_ideas)} ideas"
        )

    # Refine all ideas
    refined_ideas = await batch_refine_ideas(evaluated_ideas, iteration)

    if progress_callback:
        await progress_callback(
            "refinement",
            50,
            f"Refinement iteration {iteration}: Re-evaluating refined ideas"
        )

    # Extract refined Idea objects
    ideas_to_evaluate = [r.refined_idea for r in refined_ideas]

    # Re-evaluate refined ideas
    new_evaluations = []
    for i, idea in enumerate(ideas_to_evaluate):
        eval_result = await evaluate_single_idea(idea, budget_tier, include_stress_test=False)
        new_evaluations.append(eval_result)

        if progress_callback:
            progress = 50 + int(((i + 1) / len(ideas_to_evaluate)) * 50)
            await progress_callback(
                "refinement",
                progress,
                f"Refinement iteration {iteration}: Evaluated {i + 1}/{len(ideas_to_evaluate)}"
            )

    return new_evaluations


def check_convergence(
    previous_scores: list[float],
    current_scores: list[float],
    threshold: float = None
) -> tuple[bool, float]:
    """
    Check if refinement has converged.

    Args:
        previous_scores: Scores from previous iteration
        current_scores: Scores from current iteration
        threshold: Improvement threshold (default from config)

    Returns:
        Tuple of (is_converged, improvement_rate)
    """
    if threshold is None:
        threshold = GENERATION_CONFIG["convergence_threshold"]

    if not previous_scores or not current_scores:
        return False, 0.0

    # Calculate average improvement
    prev_avg = sum(previous_scores) / len(previous_scores)
    curr_avg = sum(current_scores) / len(current_scores)

    if prev_avg == 0:
        return False, 0.0

    improvement = (curr_avg - prev_avg) / prev_avg

    # Converged if improvement is below threshold
    is_converged = improvement < threshold

    return is_converged, improvement


def check_quality_threshold(
    evaluated_ideas: list[EvaluatedIdea],
    threshold: float = None
) -> tuple[bool, float]:
    """
    Check if top idea meets quality threshold.

    Args:
        evaluated_ideas: Evaluated ideas (should be ranked)
        threshold: Quality threshold (default from config)

    Returns:
        Tuple of (meets_threshold, top_score)
    """
    if threshold is None:
        threshold = GENERATION_CONFIG["quality_threshold"]

    if not evaluated_ideas:
        return False, 0.0

    # Get top score
    top_score = max(idea.weighted_score for idea in evaluated_ideas)

    return top_score >= threshold, top_score


async def refinement_loop(
    initial_evaluated: list[EvaluatedIdea],
    budget_tier: str,
    max_iterations: int = None,
    top_n_to_refine: int = None,
    progress_callback=None
) -> tuple[list[EvaluatedIdea], dict]:
    """
    Run the complete refinement loop until convergence.

    Args:
        initial_evaluated: Initially evaluated top ideas
        budget_tier: Budget tier for context
        max_iterations: Maximum refinement rounds (default from config)
        top_n_to_refine: Number of top ideas to refine each round
        progress_callback: Optional callback for progress updates

    Returns:
        Tuple of (final_evaluated_ideas, loop_stats)
    """
    if max_iterations is None:
        max_iterations = GENERATION_CONFIG["max_refinement_rounds"]

    if top_n_to_refine is None:
        top_n_to_refine = GENERATION_CONFIG["top_ideas_for_refinement"]

    # Initialize
    current_ideas = initial_evaluated[:top_n_to_refine]
    previous_scores = [idea.weighted_score for idea in current_ideas]

    stats = {
        "iterations": 0,
        "initial_top_score": max(previous_scores) if previous_scores else 0,
        "score_history": [previous_scores.copy()],
        "convergence_reason": None,
        "improvements": []
    }

    for iteration in range(1, max_iterations + 1):
        if progress_callback:
            await progress_callback(
                "refinement_loop",
                int((iteration - 1) / max_iterations * 100),
                f"Starting refinement round {iteration}/{max_iterations}"
            )

        # Run refinement iteration
        refined_evaluated = await run_refinement_iteration(
            current_ideas,
            budget_tier,
            iteration,
            progress_callback
        )

        # Rank refined ideas
        refined_evaluated = rank_ideas(refined_evaluated)
        current_scores = [idea.weighted_score for idea in refined_evaluated]

        # Record progress
        stats["iterations"] = iteration
        stats["score_history"].append(current_scores.copy())

        # Calculate improvement
        improvement = (
            (sum(current_scores) / len(current_scores)) -
            (sum(previous_scores) / len(previous_scores))
        ) / (sum(previous_scores) / len(previous_scores)) if previous_scores else 0

        stats["improvements"].append({
            "iteration": iteration,
            "improvement_rate": round(improvement * 100, 2),
            "top_score": max(current_scores) if current_scores else 0
        })

        # Check convergence
        is_converged, imp_rate = check_convergence(previous_scores, current_scores)
        if is_converged:
            stats["convergence_reason"] = f"Converged at iteration {iteration} (improvement: {imp_rate:.2%})"
            current_ideas = refined_evaluated
            break

        # Check quality threshold
        meets_quality, top_score = check_quality_threshold(refined_evaluated)
        if meets_quality:
            stats["convergence_reason"] = f"Quality threshold met at iteration {iteration} (score: {top_score:.2f})"
            current_ideas = refined_evaluated
            break

        # Prepare for next iteration
        previous_scores = current_scores
        current_ideas = refined_evaluated

    else:
        # Max iterations reached
        stats["convergence_reason"] = f"Max iterations ({max_iterations}) reached"

    # Final ranking
    final_ideas = rank_ideas(current_ideas)

    stats["final_top_score"] = max(idea.weighted_score for idea in final_ideas) if final_ideas else 0
    stats["total_improvement"] = (
        (stats["final_top_score"] - stats["initial_top_score"]) /
        stats["initial_top_score"] * 100
        if stats["initial_top_score"] > 0 else 0
    )

    return final_ideas, stats


async def final_polish(
    winner: EvaluatedIdea,
    budget_tier: str
) -> EvaluatedIdea:
    """
    Final polish on the winning idea with comprehensive re-evaluation.

    Args:
        winner: The winning idea
        budget_tier: Budget tier for context

    Returns:
        Final polished and evaluated idea
    """
    # One more refinement focused on making it perfect
    from generation.idea_refiner import refine_idea

    refined = await refine_idea(winner, iteration=99)

    # Full evaluation with stress test
    final_eval = await evaluate_single_idea(
        refined.refined_idea,
        budget_tier,
        include_stress_test=True
    )

    final_eval.rank = 1

    return final_eval
