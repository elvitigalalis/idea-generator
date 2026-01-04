"""
Idea refinement module - improves ideas based on judge feedback.
"""

import uuid
from typing import Optional

import sys
sys.path.append('..')

from utils.gemini_client import generate_json
from utils.prompts import REFINEMENT_PROMPT
from models import Idea, EvaluatedIdea, RefinedIdea


def format_idea_for_prompt(idea: Idea) -> str:
    """Format an idea for inclusion in a prompt."""
    return f"""Title: {idea.title}
Description: {idea.description}
Problem Solved: {idea.problem_solved}
Target Customer: {idea.target_customer}
Revenue Model: {idea.revenue_model}
Social Impact: {idea.social_impact}"""


def extract_feedback(evaluated_idea: EvaluatedIdea) -> dict:
    """
    Extract actionable feedback from judge evaluations.

    Args:
        evaluated_idea: The evaluated idea with all judge scores

    Returns:
        Dictionary with organized feedback
    """
    all_concerns = []
    all_insights = []
    improvements_needed = []

    for eval in evaluated_idea.evaluations:
        all_concerns.extend(eval.concerns)
        all_insights.append(eval.key_insight)

        # Extract specific improvements from low scores
        for score in eval.scores:
            if score.score < 6:
                improvements_needed.append(
                    f"{score.criterion}: {score.reasoning}"
                )

    # Add stress test feedback if available
    if evaluated_idea.stress_test:
        for flaw in evaluated_idea.stress_test.fundamental_flaws:
            if isinstance(flaw, dict):
                all_concerns.append(f"FLAW: {flaw.get('flaw', str(flaw))}")
            else:
                all_concerns.append(f"FLAW: {flaw}")

        for alt in evaluated_idea.stress_test.alternative_approaches:
            if isinstance(alt, dict):
                improvements_needed.append(
                    f"Consider: {alt.get('approach', str(alt))}"
                )
            else:
                improvements_needed.append(f"Consider: {alt}")

    return {
        "concerns": list(set(all_concerns))[:10],  # Dedupe and limit
        "insights": all_insights,
        "improvements_needed": improvements_needed[:8]
    }


async def refine_idea(
    evaluated_idea: EvaluatedIdea,
    iteration: int
) -> RefinedIdea:
    """
    Refine an idea based on judge feedback.

    Args:
        evaluated_idea: The evaluated idea with feedback
        iteration: Current refinement iteration number

    Returns:
        RefinedIdea with improvements
    """
    feedback = extract_feedback(evaluated_idea)

    prompt = REFINEMENT_PROMPT.format(
        original_idea=format_idea_for_prompt(evaluated_idea.idea),
        feedback="\n".join(feedback["insights"]),
        concerns="\n".join(f"- {c}" for c in feedback["concerns"]),
        improvements_needed="\n".join(f"- {i}" for i in feedback["improvements_needed"])
    )

    result = await generate_json(prompt, temperature=0.7)

    refined_data = result.get("refined_idea", {})
    refined_idea = Idea(
        id=f"{evaluated_idea.idea.id}_refined_{iteration}",
        title=refined_data.get("title", evaluated_idea.idea.title),
        description=refined_data.get("description", evaluated_idea.idea.description),
        problem_solved=refined_data.get("problem_solved", evaluated_idea.idea.problem_solved),
        target_customer=refined_data.get("target_customer", evaluated_idea.idea.target_customer),
        revenue_model=refined_data.get("revenue_model", evaluated_idea.idea.revenue_model),
        social_impact=refined_data.get("social_impact", evaluated_idea.idea.social_impact),
        budget_tier=evaluated_idea.idea.budget_tier
    )

    improvements_made = []
    for imp in result.get("improvements_made", []):
        if isinstance(imp, dict):
            improvements_made.append(f"{imp.get('concern', 'Issue')}: {imp.get('solution', 'Addressed')}")
        else:
            improvements_made.append(str(imp))

    return RefinedIdea(
        original_idea=evaluated_idea.idea,
        refined_idea=refined_idea,
        improvements_made=improvements_made,
        feedback_addressed=feedback["concerns"][:5],
        iteration=iteration
    )


async def batch_refine_ideas(
    evaluated_ideas: list[EvaluatedIdea],
    iteration: int
) -> list[RefinedIdea]:
    """
    Refine multiple ideas in parallel.

    Args:
        evaluated_ideas: List of evaluated ideas to refine
        iteration: Current refinement iteration number

    Returns:
        List of refined ideas
    """
    import asyncio

    tasks = [
        refine_idea(idea, iteration)
        for idea in evaluated_ideas
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    refined = []
    for result in results:
        if isinstance(result, Exception):
            print(f"Refinement error: {result}")
        else:
            refined.append(result)

    return refined
