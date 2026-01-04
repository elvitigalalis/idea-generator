"""
Ranking module - ranks evaluated ideas by weighted scores.
"""

from typing import Optional
import statistics

import sys
sys.path.append('..')

from models import EvaluatedIdea
from config import CRITERIA_WEIGHTS, GENERATION_CONFIG


def calculate_criteria_score(evaluated: EvaluatedIdea) -> dict:
    """
    Calculate detailed scores by criteria category.

    Args:
        evaluated: The evaluated idea

    Returns:
        Dictionary of category scores
    """
    # Map judge criteria to categories
    category_mapping = {
        "market_revenue": [
            "market_size", "revenue_potential", "willingness_to_pay",
            "problem_urgency", "customer_accessibility"
        ],
        "social_impact": [
            "impact_magnitude", "environmental_sustainability",
            "long_term_sustainability", "measurable_outcomes"
        ],
        "feasibility": [
            "execution_complexity", "resource_requirements", "time_to_market",
            "technical_feasibility", "budget_alignment", "build_vs_buy"
        ],
        "differentiation": [
            "scalability", "investment_attractiveness", "competitive_differentiation",
            "technical_moat", "operational_scalability"
        ]
    }

    category_scores = {}

    for category, criteria_list in category_mapping.items():
        scores = []
        for eval in evaluated.evaluations:
            for score in eval.scores:
                if score.criterion in criteria_list:
                    scores.append(score.score)

        if scores:
            category_scores[category] = round(statistics.mean(scores), 2)
        else:
            category_scores[category] = 5.0  # Default

    return category_scores


def calculate_final_score(evaluated: EvaluatedIdea) -> float:
    """
    Calculate final weighted score considering all factors.

    Args:
        evaluated: The evaluated idea

    Returns:
        Final weighted score
    """
    # Get category scores
    category_scores = calculate_criteria_score(evaluated)

    # Calculate weighted sum
    final = 0
    for category, weight in CRITERIA_WEIGHTS.items():
        final += category_scores.get(category, 5.0) * weight

    # Apply stress test modifier
    if evaluated.stress_test:
        if evaluated.stress_test.recommendation == "kill":
            final *= 0.4  # Heavy penalty
        elif evaluated.stress_test.recommendation == "revise":
            final *= 0.85  # Moderate penalty
        elif evaluated.stress_test.recommendation == "proceed":
            final *= 1.05  # Small bonus for surviving stress test

    return round(final, 2)


def rank_ideas(
    evaluated_ideas: list[EvaluatedIdea],
    top_n: Optional[int] = None
) -> list[EvaluatedIdea]:
    """
    Rank ideas by their final scores.

    Args:
        evaluated_ideas: List of evaluated ideas
        top_n: Number of top ideas to return (None = all)

    Returns:
        Sorted list of evaluated ideas with ranks assigned
    """
    # Recalculate final scores
    for idea in evaluated_ideas:
        idea.weighted_score = calculate_final_score(idea)

    # Sort by score descending
    sorted_ideas = sorted(
        evaluated_ideas,
        key=lambda x: x.weighted_score,
        reverse=True
    )

    # Assign ranks
    for i, idea in enumerate(sorted_ideas):
        idea.rank = i + 1

    if top_n:
        return sorted_ideas[:top_n]
    return sorted_ideas


def get_ranking_insights(ranked_ideas: list[EvaluatedIdea]) -> dict:
    """
    Generate insights about the ranking results.

    Args:
        ranked_ideas: List of ranked ideas

    Returns:
        Dictionary of ranking insights
    """
    if not ranked_ideas:
        return {"error": "No ideas to analyze"}

    scores = [i.weighted_score for i in ranked_ideas]

    # Calculate score distribution
    insights = {
        "total_ranked": len(ranked_ideas),
        "score_stats": {
            "max": max(scores),
            "min": min(scores),
            "mean": round(statistics.mean(scores), 2),
            "median": round(statistics.median(scores), 2),
            "std_dev": round(statistics.stdev(scores), 2) if len(scores) > 1 else 0
        },
        "quality_tiers": {
            "excellent": len([s for s in scores if s >= 8]),
            "good": len([s for s in scores if 6 <= s < 8]),
            "average": len([s for s in scores if 4 <= s < 6]),
            "below_average": len([s for s in scores if s < 4])
        }
    }

    # Identify standout winner
    if len(ranked_ideas) >= 2:
        gap = ranked_ideas[0].weighted_score - ranked_ideas[1].weighted_score
        insights["clear_winner"] = gap >= 0.5
        insights["winner_gap"] = round(gap, 2)
    else:
        insights["clear_winner"] = True
        insights["winner_gap"] = 0

    # Top idea summary
    top = ranked_ideas[0]
    insights["winner_summary"] = {
        "title": top.idea.title,
        "score": top.weighted_score,
        "category_scores": calculate_criteria_score(top),
        "key_strengths": _identify_strengths(top),
        "key_concerns": _identify_concerns(top)
    }

    return insights


def _identify_strengths(evaluated: EvaluatedIdea) -> list[str]:
    """Identify key strengths from evaluations."""
    strengths = []
    for eval in evaluated.evaluations:
        for score in eval.scores:
            if score.score >= 8:
                strengths.append(f"{score.criterion}: {score.score}/10")
        if eval.overall_score >= 8:
            strengths.append(eval.key_insight)

    return list(set(strengths))[:5]


def _identify_concerns(evaluated: EvaluatedIdea) -> list[str]:
    """Identify key concerns from evaluations."""
    concerns = []
    for eval in evaluated.evaluations:
        concerns.extend(eval.concerns)

    if evaluated.stress_test:
        concerns.extend(evaluated.stress_test.fundamental_flaws[:3])

    return list(set(concerns))[:5]


def compare_ideas(
    idea1: EvaluatedIdea,
    idea2: EvaluatedIdea
) -> dict:
    """
    Compare two ideas side by side.

    Args:
        idea1: First idea
        idea2: Second idea

    Returns:
        Comparison dictionary
    """
    scores1 = calculate_criteria_score(idea1)
    scores2 = calculate_criteria_score(idea2)

    comparison = {
        "idea1": {
            "title": idea1.idea.title,
            "total_score": idea1.weighted_score,
            "category_scores": scores1
        },
        "idea2": {
            "title": idea2.idea.title,
            "total_score": idea2.weighted_score,
            "category_scores": scores2
        },
        "differences": {},
        "recommendation": ""
    }

    # Calculate differences by category
    for category in CRITERIA_WEIGHTS.keys():
        diff = scores1.get(category, 5) - scores2.get(category, 5)
        comparison["differences"][category] = round(diff, 2)

    # Determine recommendation
    if idea1.weighted_score > idea2.weighted_score + 0.5:
        comparison["recommendation"] = f"{idea1.idea.title} is clearly stronger"
    elif idea2.weighted_score > idea1.weighted_score + 0.5:
        comparison["recommendation"] = f"{idea2.idea.title} is clearly stronger"
    else:
        comparison["recommendation"] = "Both ideas are comparable - consider other factors"

    return comparison
