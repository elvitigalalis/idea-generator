"""
Pydantic models for type safety and API contracts.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class BusinessModel(str, Enum):
    B2B = "B2B"
    B2C = "B2C"
    B2B2C = "B2B2C"
    B2G = "B2G"
    MARKETPLACE = "marketplace"
    SUBSCRIPTION = "subscription"
    FREEMIUM = "freemium"
    TRANSACTION_FEE = "transaction_fee"
    LICENSING = "licensing"
    HYBRID = "hybrid"


class ImpactFocus(str, Enum):
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    ENVIRONMENT = "environment"
    FINANCIAL_INCLUSION = "financial_inclusion"
    FOOD_SECURITY = "food_security"
    MENTAL_HEALTH = "mental_health"
    ACCESSIBILITY = "accessibility"
    COMMUNITY = "community_building"
    SUSTAINABLE_CONSUMPTION = "sustainable_consumption"
    WORKFORCE = "workforce_development"
    GENERAL = "general"


class TechPreference(str, Enum):
    NO_CODE = "no_code"
    LOW_CODE = "low_code"
    CUSTOM = "custom"
    AI_POWERED = "ai_powered"
    ANY = "any"


class Preferences(BaseModel):
    """User preferences for idea generation."""
    business_model: Optional[BusinessModel] = None
    impact_focus: Optional[ImpactFocus] = None
    tech_preference: Optional[TechPreference] = None


class GenerationRequest(BaseModel):
    """Request body for idea generation."""
    topic: Optional[str] = Field(
        default=None,
        description="Topic or domain for ideas. Leave blank for niche discovery."
    )
    budget: Optional[str] = Field(
        default=None,
        description="Budget constraint (e.g., '$5000', 'bootstrapped', '50k')"
    )
    preferences: Optional[Preferences] = None


class JudgeScore(BaseModel):
    """Score from a single judge on a single criterion."""
    criterion: str
    score: float = Field(ge=1, le=10)
    reasoning: str


class JudgeEvaluation(BaseModel):
    """Complete evaluation from one judge."""
    judge_id: str
    judge_name: str
    scores: list[JudgeScore]
    overall_score: float
    key_insight: str
    concerns: list[str]


class StressTestResult(BaseModel):
    """Result from stress testing an idea."""
    fundamental_flaws: list[str]
    flaw_count: int
    alternative_approaches: list[str]
    survival_score: float = Field(ge=0, le=10)
    recommendation: str  # "kill", "revise", "proceed"


class Idea(BaseModel):
    """A single startup idea with metadata."""
    id: str
    title: str
    description: str
    problem_solved: str
    target_customer: str
    revenue_model: str
    social_impact: Optional[str] = None
    budget_tier: Optional[str] = None


class EvaluatedIdea(BaseModel):
    """An idea with all judge evaluations."""
    idea: Idea
    evaluations: list[JudgeEvaluation]
    stress_test: Optional[StressTestResult] = None
    weighted_score: float
    rank: Optional[int] = None
    feedback_for_refinement: Optional[str] = None


class RefinedIdea(BaseModel):
    """An idea after refinement based on feedback."""
    original_idea: Idea
    refined_idea: Idea
    improvements_made: list[str]
    feedback_addressed: list[str]
    iteration: int


class MarketAnalysis(BaseModel):
    """Market analysis for feasibility report."""
    tam: str  # Total Addressable Market
    sam: str  # Serviceable Addressable Market
    som: str  # Serviceable Obtainable Market
    primary_customers: list[str]
    customer_pain_points: list[str]
    willingness_to_pay: str
    acquisition_channels: list[str]


class SocialImpactAssessment(BaseModel):
    """Social impact assessment for feasibility report."""
    beneficiaries: list[str]
    impact_type: str
    measurable_outcomes: list[str]
    sustainability_model: str
    sdg_alignment: list[str]  # UN Sustainable Development Goals


class RiskAssessment(BaseModel):
    """Risk assessment for feasibility report."""
    key_risks: list[dict]  # {"risk": str, "likelihood": str, "mitigation": str}
    regulatory_concerns: list[str]
    competitive_threats: list[str]
    execution_risks: list[str]


class ActionItem(BaseModel):
    """Action item for 90-day plan."""
    week: str
    action: str
    deliverable: str
    resources_needed: str


class FeasibilityReport(BaseModel):
    """Complete business feasibility report."""
    executive_summary: str
    problem_statement: str
    solution_overview: str
    market_analysis: MarketAnalysis
    social_impact: SocialImpactAssessment
    revenue_model: dict
    competitive_landscape: str
    technical_requirements: dict
    risk_assessment: RiskAssessment
    go_to_market: str
    action_plan_90_days: list[ActionItem]
    final_recommendation: str
    confidence_score: float


class GenerationResult(BaseModel):
    """Final result of the idea generation process."""
    job_id: str
    status: str
    topic_used: str
    budget_tier: str
    total_ideas_generated: int
    ideas_after_screening: int
    refinement_rounds: int
    top_ideas: list[EvaluatedIdea]
    winner: EvaluatedIdea
    feasibility_report: FeasibilityReport
    runner_ups: list[EvaluatedIdea]


class JobStatus(BaseModel):
    """Status of a running generation job."""
    job_id: str
    status: str  # "running", "completed", "failed"
    phase: str
    progress_percent: float
    current_action: str
    ideas_generated: int
    ideas_evaluated: int
    refinement_round: int
    errors: list[str]
