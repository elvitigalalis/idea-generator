"""
Business Feasibility Report generator - creates comprehensive business analysis.
"""

from typing import Optional

import sys
sys.path.append('..')

from utils.gemini_client import generate_json
from utils.prompts import FEASIBILITY_REPORT_PROMPT
from models import (
    EvaluatedIdea, FeasibilityReport, MarketAnalysis,
    SocialImpactAssessment, RiskAssessment, ActionItem
)


def format_idea_for_report(idea: EvaluatedIdea) -> str:
    """Format idea details for feasibility report prompt."""
    return f"""Title: {idea.idea.title}
Description: {idea.idea.description}
Problem Solved: {idea.idea.problem_solved}
Target Customer: {idea.idea.target_customer}
Revenue Model: {idea.idea.revenue_model}
Social Impact: {idea.idea.social_impact}

Overall Score: {idea.weighted_score}/10
Rank: #{idea.rank}"""


def format_evaluations_summary(idea: EvaluatedIdea) -> str:
    """Summarize all judge evaluations for the report."""
    summary_parts = []

    for eval in idea.evaluations:
        judge_summary = f"**{eval.judge_name}** (Score: {eval.overall_score}/10)\n"
        judge_summary += f"Key Insight: {eval.key_insight}\n"
        if eval.concerns:
            judge_summary += f"Concerns: {', '.join(eval.concerns[:3])}\n"
        summary_parts.append(judge_summary)

    if idea.stress_test:
        stress_summary = f"**Stress Test** (Survival Score: {idea.stress_test.survival_score}/10)\n"
        stress_summary += f"Recommendation: {idea.stress_test.recommendation}\n"
        if idea.stress_test.fundamental_flaws:
            stress_summary += f"Flaws Identified: {', '.join(idea.stress_test.fundamental_flaws[:3])}\n"
        summary_parts.append(stress_summary)

    return "\n".join(summary_parts)


async def generate_feasibility_report(
    winner: EvaluatedIdea,
    budget_tier: str,
    runner_ups: list[EvaluatedIdea] = None
) -> FeasibilityReport:
    """
    Generate a comprehensive business feasibility report.

    Args:
        winner: The winning idea to analyze
        budget_tier: Budget tier for context
        runner_ups: Optional list of runner-up ideas for comparison

    Returns:
        Complete FeasibilityReport
    """
    prompt = FEASIBILITY_REPORT_PROMPT.format(
        idea_details=format_idea_for_report(winner),
        evaluations_summary=format_evaluations_summary(winner),
        budget_tier=budget_tier
    )

    result = await generate_json(prompt, temperature=0.5)

    # Parse market analysis
    market_data = result.get("market_analysis", {})
    market_analysis = MarketAnalysis(
        tam=market_data.get("tam", "Unknown"),
        sam=market_data.get("sam", "Unknown"),
        som=market_data.get("som", "Unknown"),
        primary_customers=market_data.get("primary_customers", []),
        customer_pain_points=market_data.get("customer_pain_points", []),
        willingness_to_pay=market_data.get("willingness_to_pay", "Unknown"),
        acquisition_channels=market_data.get("acquisition_channels", [])
    )

    # Parse social impact assessment
    impact_data = result.get("social_impact_assessment", {})
    social_impact = SocialImpactAssessment(
        beneficiaries=impact_data.get("beneficiaries", []),
        impact_type=impact_data.get("impact_type", "Unknown"),
        measurable_outcomes=impact_data.get("measurable_outcomes", []),
        sustainability_model=impact_data.get("sustainability_model", "Unknown"),
        sdg_alignment=impact_data.get("sdg_alignment", [])
    )

    # Parse risk assessment
    risk_data = result.get("risk_assessment", {})
    risk_assessment = RiskAssessment(
        key_risks=risk_data.get("key_risks", []),
        regulatory_concerns=risk_data.get("regulatory_concerns", []),
        competitive_threats=risk_data.get("competitive_threats", []),
        execution_risks=risk_data.get("execution_risks", [])
    )

    # Parse action plan
    action_plan_data = result.get("action_plan_90_days", [])
    action_plan = []
    for action in action_plan_data:
        if isinstance(action, dict):
            action_plan.append(ActionItem(
                week=action.get("week", "TBD"),
                action=action.get("action", ""),
                deliverable=action.get("deliverable", ""),
                resources_needed=action.get("resources", "")
            ))

    # Build complete report
    report = FeasibilityReport(
        executive_summary=result.get("executive_summary", ""),
        problem_statement=result.get("problem_statement", ""),
        solution_overview=result.get("solution_overview", ""),
        market_analysis=market_analysis,
        social_impact=social_impact,
        revenue_model=result.get("revenue_model", {}),
        competitive_landscape=result.get("competitive_landscape", ""),
        technical_requirements=result.get("technical_requirements", {}),
        risk_assessment=risk_assessment,
        go_to_market=result.get("go_to_market_strategy", ""),
        action_plan_90_days=action_plan,
        final_recommendation=result.get("final_recommendation", ""),
        confidence_score=float(result.get("confidence_score", 7.0))
    )

    return report


def format_report_as_markdown(report: FeasibilityReport, idea: EvaluatedIdea) -> str:
    """
    Format the feasibility report as markdown for display.

    Args:
        report: The feasibility report
        idea: The idea being reported on

    Returns:
        Markdown formatted report
    """
    md = f"""# Business Feasibility Report

## {idea.idea.title}

**Overall Score: {idea.weighted_score}/10**

---

## Executive Summary

{report.executive_summary}

---

## Problem Statement

{report.problem_statement}

## Solution Overview

{report.solution_overview}

---

## Market Analysis

### Total Addressable Market (TAM)
{report.market_analysis.tam}

### Serviceable Addressable Market (SAM)
{report.market_analysis.sam}

### Serviceable Obtainable Market (SOM)
{report.market_analysis.som}

### Primary Customers
"""

    for customer in report.market_analysis.primary_customers:
        md += f"- {customer}\n"

    md += """
### Customer Pain Points
"""
    for pain in report.market_analysis.customer_pain_points:
        md += f"- {pain}\n"

    md += f"""
### Willingness to Pay
{report.market_analysis.willingness_to_pay}

### Customer Acquisition Channels
"""
    for channel in report.market_analysis.acquisition_channels:
        md += f"- {channel}\n"

    md += f"""
---

## Social Impact Assessment

### Beneficiaries
"""
    for ben in report.social_impact.beneficiaries:
        md += f"- {ben}\n"

    md += f"""
### Impact Type
{report.social_impact.impact_type}

### Measurable Outcomes
"""
    for outcome in report.social_impact.measurable_outcomes:
        md += f"- {outcome}\n"

    md += f"""
### Sustainability Model
{report.social_impact.sustainability_model}

### UN SDG Alignment
"""
    for sdg in report.social_impact.sdg_alignment:
        md += f"- {sdg}\n"

    md += f"""
---

## Revenue Model

"""
    if isinstance(report.revenue_model, dict):
        for key, value in report.revenue_model.items():
            md += f"**{key.replace('_', ' ').title()}**: {value}\n\n"

    md += f"""
---

## Competitive Landscape

{report.competitive_landscape}

---

## Technical Requirements

"""
    if isinstance(report.technical_requirements, dict):
        for key, value in report.technical_requirements.items():
            if isinstance(value, list):
                md += f"**{key.replace('_', ' ').title()}**:\n"
                for item in value:
                    md += f"- {item}\n"
                md += "\n"
            else:
                md += f"**{key.replace('_', ' ').title()}**: {value}\n\n"

    md += f"""
---

## Risk Assessment

### Key Risks
"""
    for risk in report.risk_assessment.key_risks:
        if isinstance(risk, dict):
            md += f"- **{risk.get('risk', 'Unknown')}** (Likelihood: {risk.get('likelihood', 'Unknown')})\n"
            md += f"  - Mitigation: {risk.get('mitigation', 'TBD')}\n"
        else:
            md += f"- {risk}\n"

    md += """
### Regulatory Concerns
"""
    for concern in report.risk_assessment.regulatory_concerns:
        md += f"- {concern}\n"

    md += """
### Competitive Threats
"""
    for threat in report.risk_assessment.competitive_threats:
        md += f"- {threat}\n"

    md += """
### Execution Risks
"""
    for risk in report.risk_assessment.execution_risks:
        md += f"- {risk}\n"

    md += f"""
---

## Go-to-Market Strategy

{report.go_to_market}

---

## 90-Day Action Plan

| Week | Action | Deliverable | Resources |
|------|--------|-------------|-----------|
"""
    for action in report.action_plan_90_days:
        md += f"| {action.week} | {action.action} | {action.deliverable} | {action.resources_needed} |\n"

    md += f"""
---

## Final Recommendation

{report.final_recommendation}

**Confidence Score: {report.confidence_score}/10**

---

*Report generated by Idea Generator AI*
"""

    return md
