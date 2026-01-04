"""
Configuration constants and settings for the Idea Generator system.
"""

# Budget tiers with constraints
BUDGET_TIERS = {
    "bootstrapped": {
        "range": (0, 1000),
        "constraints": [
            "Solo founder only",
            "No-code/low-code tools required",
            "Organic growth only - no paid marketing",
            "Free tier services only",
            "Side project timeline acceptable"
        ],
        "tech_options": ["no-code", "low-code", "open-source only"],
        "team_size": 1
    },
    "minimal": {
        "range": (1000, 10000),
        "constraints": [
            "1-2 person team maximum",
            "Limited custom development",
            "Guerrilla marketing tactics",
            "Lean MVP approach required"
        ],
        "tech_options": ["low-code", "simple custom", "templates"],
        "team_size": 2
    },
    "modest": {
        "range": (10000, 50000),
        "constraints": [
            "Small part-time team possible",
            "Custom development feasible",
            "Small advertising budget",
            "Professional tools accessible"
        ],
        "tech_options": ["custom development", "paid services"],
        "team_size": 3
    },
    "moderate": {
        "range": (50000, 200000),
        "constraints": [
            "Full-time small team viable",
            "Professional development",
            "Moderate marketing budget",
            "Infrastructure investment possible"
        ],
        "tech_options": ["full custom", "scalable infrastructure"],
        "team_size": 5
    },
    "well_funded": {
        "range": (200000, 1000000),
        "constraints": [
            "Complete team buildable",
            "Comprehensive go-to-market",
            "Significant runway",
            "Enterprise-grade solutions"
        ],
        "tech_options": ["any technology", "enterprise solutions"],
        "team_size": 15
    },
    "venture_scale": {
        "range": (1000000, float('inf')),
        "constraints": [
            "No resource constraints",
            "Optimize for growth over efficiency",
            "Aggressive market capture",
            "Top-tier talent acquisition"
        ],
        "tech_options": ["unlimited"],
        "team_size": 50
    }
}

# Judge weights for final scoring
JUDGE_WEIGHTS = {
    "vc": 0.20,              # The VC - ROI focus
    "operator": 0.20,        # The Operator - execution focus
    "impact_investor": 0.20, # The Impact Investor - social impact
    "market_validator": 0.20,# The Market Validator - customer demand
    "tech_realist": 0.10,    # The Tech Realist - technical feasibility
    "devils_advocate": 0.10  # The Devil's Advocate - risk/flaws
}

# Evaluation criteria categories
CRITERIA_WEIGHTS = {
    "market_revenue": 0.30,
    "social_impact": 0.25,
    "feasibility": 0.25,
    "differentiation": 0.20
}

# Generation settings
GENERATION_CONFIG = {
    "ideas_per_batch": 25,
    "total_batches": 5,  # 125 ideas total
    "temperature_generation": 0.9,
    "temperature_evaluation": 0.3,
    "temperature_refinement": 0.7,
    "max_refinement_rounds": 3,
    "convergence_threshold": 0.05,  # 5% improvement threshold
    "quality_threshold": 8.0,  # Target score for "perfect" idea
    "top_ideas_for_refinement": 10,
    "final_top_ideas": 3
}

# Screening thresholds
SCREENING_CONFIG = {
    "min_feasibility_score": 4,
    "min_clarity_score": 5,
    "min_uniqueness_score": 4,
    "pass_rate_target": 0.5  # Aim to pass ~50% of ideas
}

# Stress test configuration (the 99% killer)
STRESS_TEST_CONFIG = {
    "fundamental_flaw_checks": [
        "Is this solving a real problem people actually have?",
        "Would people actually pay money for this, or just say they would?",
        "Has this been tried before and failed? Why?",
        "What's the simplest reason this wouldn't work?",
        "Is the timing right, or is this too early/too late?",
        "Can this actually be built with current technology?",
        "Is there a chicken-and-egg problem (marketplace, network effects)?",
        "Are there regulatory or legal showstoppers?",
        "Is the unit economics fundamentally broken?",
        "Could a big player crush this instantly if successful?"
    ],
    "alternative_approaches": [
        "Could this problem be solved without building anything new?",
        "Is there a 10x simpler way to achieve the same outcome?",
        "What if we approached this from the opposite direction?",
        "Who else is trying to solve this and how?",
        "What would a contrarian approach look like?"
    ],
    "kill_threshold": 3  # If 3+ fundamental flaws, idea is killed
}

# Impact focus areas
IMPACT_AREAS = [
    "education",
    "healthcare",
    "environment",
    "financial_inclusion",
    "food_security",
    "mental_health",
    "accessibility",
    "community_building",
    "sustainable_consumption",
    "workforce_development"
]

# Business model types
BUSINESS_MODELS = [
    "B2B",      # Business to Business
    "B2C",      # Business to Consumer
    "B2B2C",    # Business to Business to Consumer
    "B2G",      # Business to Government
    "marketplace",
    "subscription",
    "freemium",
    "transaction_fee",
    "licensing",
    "hybrid"
]

# Gemini model configuration
GEMINI_CONFIG = {
    "model": "gemini-2.0-flash",
    "max_retries": 3,
    "retry_delay": 2,  # seconds
    "request_timeout": 60  # seconds
}
