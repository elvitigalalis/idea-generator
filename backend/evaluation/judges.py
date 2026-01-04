"""
Judge personas for idea evaluation - Shark Tank style expert panel.
"""

from dataclasses import dataclass
from typing import Callable
import asyncio

import sys
sys.path.append('..')

from utils.gemini_client import generate_json
from utils.prompts import (
    JUDGE_VC_PROMPT,
    JUDGE_OPERATOR_PROMPT,
    JUDGE_IMPACT_PROMPT,
    JUDGE_MARKET_PROMPT,
    JUDGE_TECH_PROMPT,
    JUDGE_DEVILS_ADVOCATE_PROMPT
)
from models import Idea, JudgeScore, JudgeEvaluation
from config import JUDGE_WEIGHTS


@dataclass
class JudgePersona:
    """Definition of a judge persona."""
    id: str
    name: str
    title: str
    background: str
    focus: str
    prompt_template: str
    weight: float
    criteria: list[str]


# Define all judge personas
JUDGES = {
    "vc": JudgePersona(
        id="vc",
        name="Victoria Chen",
        title="Venture Capitalist",
        background="20 years in VC, funded 50+ startups, 8 unicorns",
        focus="ROI, scalability, exit potential",
        prompt_template=JUDGE_VC_PROMPT,
        weight=JUDGE_WEIGHTS["vc"],
        criteria=["market_size", "scalability", "revenue_potential", "investment_attractiveness"]
    ),
    "operator": JudgePersona(
        id="operator",
        name="Marcus Johnson",
        title="Serial Entrepreneur",
        background="Built and sold 3 companies, bootstrapped to $5M ARR",
        focus="Execution, operations, lean startup",
        prompt_template=JUDGE_OPERATOR_PROMPT,
        weight=JUDGE_WEIGHTS["operator"],
        criteria=["execution_complexity", "resource_requirements", "time_to_market", "operational_scalability"]
    ),
    "impact_investor": JudgePersona(
        id="impact_investor",
        name="Dr. Amara Okonkwo",
        title="Impact Investor & Advisor",
        background="PhD Development Economics, advised 100+ social enterprises",
        focus="Social impact, sustainability, measurable outcomes",
        prompt_template=JUDGE_IMPACT_PROMPT,
        weight=JUDGE_WEIGHTS["impact_investor"],
        criteria=["impact_magnitude", "environmental_sustainability", "long_term_sustainability", "measurable_outcomes"]
    ),
    "market_validator": JudgePersona(
        id="market_validator",
        name="Sarah Martinez",
        title="Consumer Insights Director",
        background="15 years market research, product-market fit specialist",
        focus="Customer demand, willingness to pay, validation",
        prompt_template=JUDGE_MARKET_PROMPT,
        weight=JUDGE_WEIGHTS["market_validator"],
        criteria=["problem_urgency", "willingness_to_pay", "customer_accessibility", "competitive_differentiation"]
    ),
    "tech_realist": JudgePersona(
        id="tech_realist",
        name="Raj Patel",
        title="CTO & Technical Architect",
        background="CTO 4x, built systems for millions of users",
        focus="Technical feasibility, build complexity, tech stack",
        prompt_template=JUDGE_TECH_PROMPT,
        weight=JUDGE_WEIGHTS["tech_realist"],
        criteria=["technical_feasibility", "budget_alignment", "build_vs_buy", "technical_moat"]
    ),
    "devils_advocate": JudgePersona(
        id="devils_advocate",
        name="Diana Wolf",
        title="Risk Analyst",
        background="Studied 1000+ startup failures, finds fatal flaws",
        focus="Risk, failure modes, hidden challenges",
        prompt_template=JUDGE_DEVILS_ADVOCATE_PROMPT,
        weight=JUDGE_WEIGHTS["devils_advocate"],
        criteria=["risk_level", "regulatory_concerns", "market_timing", "hidden_complexity"]
    )
}


def format_idea_details(idea: Idea) -> str:
    """Format idea for judge evaluation prompts."""
    return f"""IDEA: {idea.title}

DESCRIPTION: {idea.description}

PROBLEM SOLVED: {idea.problem_solved}

TARGET CUSTOMER: {idea.target_customer}

REVENUE MODEL: {idea.revenue_model}

SOCIAL IMPACT: {idea.social_impact}"""


async def get_judge_evaluation(
    idea: Idea,
    judge: JudgePersona,
    budget_tier: str
) -> JudgeEvaluation:
    """
    Get evaluation from a single judge.

    Args:
        idea: The idea to evaluate
        judge: The judge persona
        budget_tier: Budget tier for context

    Returns:
        JudgeEvaluation with scores and insights
    """
    prompt = judge.prompt_template.format(
        idea_details=format_idea_details(idea),
        budget_tier=budget_tier
    )

    result = await generate_json(prompt, temperature=0.3)

    # Parse scores
    scores = []
    scores_data = result.get("scores", {})

    for criterion in judge.criteria:
        criterion_data = scores_data.get(criterion, {})
        if isinstance(criterion_data, dict):
            score_value = float(criterion_data.get("score", 5))
            reasoning = criterion_data.get("reasoning", "No reasoning provided")
        else:
            score_value = float(criterion_data) if criterion_data else 5.0
            reasoning = "Score only"

        scores.append(JudgeScore(
            criterion=criterion,
            score=max(1, min(10, score_value)),  # Clamp to 1-10
            reasoning=reasoning
        ))

    # Calculate overall score as average of criteria scores
    overall = sum(s.score for s in scores) / len(scores) if scores else 5.0

    # Get concerns list
    concerns = result.get("concerns", [])
    if not isinstance(concerns, list):
        concerns = [str(concerns)]

    return JudgeEvaluation(
        judge_id=judge.id,
        judge_name=f"{judge.name} ({judge.title})",
        scores=scores,
        overall_score=round(overall, 2),
        key_insight=result.get("key_insight", "No key insight"),
        concerns=concerns[:5]  # Limit to 5 concerns
    )


async def evaluate_with_all_judges(
    idea: Idea,
    budget_tier: str,
    judges_to_use: list[str] = None
) -> list[JudgeEvaluation]:
    """
    Evaluate an idea with all judges in parallel.

    Args:
        idea: The idea to evaluate
        budget_tier: Budget tier for context
        judges_to_use: List of judge IDs to use (default: all)

    Returns:
        List of JudgeEvaluation from all judges
    """
    if judges_to_use is None:
        judges_to_use = list(JUDGES.keys())

    tasks = [
        get_judge_evaluation(idea, JUDGES[judge_id], budget_tier)
        for judge_id in judges_to_use
        if judge_id in JUDGES
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    evaluations = []
    for result in results:
        if isinstance(result, Exception):
            print(f"Judge evaluation error: {result}")
        else:
            evaluations.append(result)

    return evaluations


def calculate_weighted_score(evaluations: list[JudgeEvaluation]) -> float:
    """
    Calculate weighted average score from all judges.

    Args:
        evaluations: List of judge evaluations

    Returns:
        Weighted average score
    """
    if not evaluations:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0

    for eval in evaluations:
        judge_id = eval.judge_id
        weight = JUDGES.get(judge_id, JudgePersona(
            id="unknown", name="Unknown", title="", background="",
            focus="", prompt_template="", weight=0.1, criteria=[]
        )).weight

        weighted_sum += eval.overall_score * weight
        total_weight += weight

    if total_weight == 0:
        return sum(e.overall_score for e in evaluations) / len(evaluations)

    return round(weighted_sum / total_weight, 2)


def get_all_judges_info() -> list[dict]:
    """Get information about all judges for display."""
    return [
        {
            "id": j.id,
            "name": j.name,
            "title": j.title,
            "background": j.background,
            "focus": j.focus,
            "weight": j.weight,
            "criteria": j.criteria
        }
        for j in JUDGES.values()
    ]
