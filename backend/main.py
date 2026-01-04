"""
Idea Generator - Main FastAPI Application

A sophisticated AI-powered startup idea generation and validation system.
Generates 100+ ideas, filters through expert judges, and iteratively
refines until a winning idea emerges with full business feasibility analysis.
"""

import asyncio
import uuid
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import GENERATION_CONFIG, BUDGET_TIERS
from models import (
    GenerationRequest, GenerationResult, JobStatus,
    EvaluatedIdea, Preferences
)
from discovery.niche_finder import parse_budget, get_topic_or_discover
from generation.idea_generator import generate_all_ideas, deduplicate_ideas
from evaluation.evaluator import full_evaluation_pipeline
from evaluation.judges import get_all_judges_info
from ranking.ranker import rank_ideas, get_ranking_insights
from refinement.refinement_loop import refinement_loop, final_polish
from reporting.feasibility import generate_feasibility_report, format_report_as_markdown


# Job storage (in production, use Redis or database)
jobs: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print("🚀 Idea Generator starting up...")
    yield
    print("👋 Idea Generator shutting down...")


app = FastAPI(
    title="Idea Generator",
    description="AI-powered startup idea generation and validation system",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

async def update_job_status(
    job_id: str,
    phase: str,
    progress: float,
    message: str
):
    """Update job status for progress tracking."""
    if job_id in jobs:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["phase"] = phase
        jobs[job_id]["progress"] = progress
        jobs[job_id]["current_action"] = message


async def run_generation_pipeline(
    job_id: str,
    request: GenerationRequest
):
    """
    Run the complete idea generation pipeline as a background task.

    Phases:
    1. Topic Discovery (if needed)
    2. Idea Generation (100+ ideas)
    3. Initial Screening
    4. Stress Testing (99% killer)
    5. Expert Panel Evaluation
    6. Refinement Loop
    7. Final Selection & Report
    """
    try:
        # Initialize job
        jobs[job_id]["status"] = "running"
        jobs[job_id]["started_at"] = asyncio.get_event_loop().time()

        # Parse budget
        budget_tier, budget_config = await parse_budget(request.budget)
        jobs[job_id]["budget_tier"] = budget_tier

        # =================================================================
        # PHASE 1: Topic Discovery
        # =================================================================
        await update_job_status(job_id, "discovery", 5, "Analyzing topic and market")

        preferences = request.preferences or Preferences()
        topic_result = await get_topic_or_discover(
            topic=request.topic,
            budget_tier=budget_tier,
            budget_config=budget_config,
            tech_preference=preferences.tech_preference.value if preferences.tech_preference else "any",
            impact_focus=preferences.impact_focus.value if preferences.impact_focus else "general"
        )

        topic = topic_result["topic"]
        jobs[job_id]["topic"] = topic
        jobs[job_id]["topic_discovered"] = topic_result["was_discovered"]

        # =================================================================
        # PHASE 2: Idea Generation
        # =================================================================
        await update_job_status(job_id, "generation", 10, f"Generating ideas for: {topic}")

        ideas = await generate_all_ideas(
            topic=topic,
            budget_tier=budget_tier,
            budget_config=budget_config,
            total_ideas=125,
            ideas_per_batch=25,
            business_model=preferences.business_model.value if preferences.business_model else None,
            impact_focus=preferences.impact_focus.value if preferences.impact_focus else None,
            tech_preference=preferences.tech_preference.value if preferences.tech_preference else None,
            progress_callback=lambda phase, prog, msg: update_job_status(
                job_id, "generation", 10 + prog * 0.2, msg
            )
        )

        # Deduplicate
        ideas = await deduplicate_ideas(ideas)
        jobs[job_id]["ideas_generated"] = len(ideas)

        # =================================================================
        # PHASE 3-5: Evaluation Pipeline (Screen -> Stress Test -> Judges)
        # =================================================================
        await update_job_status(job_id, "evaluation", 30, "Running evaluation pipeline")

        evaluated_ideas, eval_stats = await full_evaluation_pipeline(
            ideas=ideas,
            budget_tier=budget_tier,
            progress_callback=lambda phase, prog, msg: update_job_status(
                job_id, phase, 30 + prog * 0.35, msg
            )
        )

        jobs[job_id]["ideas_after_screening"] = eval_stats.get("after_screening", 0)
        jobs[job_id]["ideas_after_stress_test"] = eval_stats.get("after_stress_test", 0)
        jobs[job_id]["ideas_evaluated"] = len(evaluated_ideas)

        if not evaluated_ideas:
            raise Exception("No ideas survived evaluation. Try a different topic or budget.")

        # =================================================================
        # PHASE 6: Refinement Loop
        # =================================================================
        await update_job_status(job_id, "refinement", 65, "Refining top ideas")

        top_for_refinement = evaluated_ideas[:GENERATION_CONFIG["top_ideas_for_refinement"]]

        refined_ideas, refinement_stats = await refinement_loop(
            initial_evaluated=top_for_refinement,
            budget_tier=budget_tier,
            progress_callback=lambda phase, prog, msg: update_job_status(
                job_id, "refinement", 65 + prog * 0.2, msg
            )
        )

        jobs[job_id]["refinement_rounds"] = refinement_stats["iterations"]

        # =================================================================
        # PHASE 7: Final Selection & Report
        # =================================================================
        await update_job_status(job_id, "reporting", 85, "Generating feasibility report")

        # Final ranking
        final_ranked = rank_ideas(refined_ideas)
        winner = final_ranked[0]

        # Final polish on winner
        winner = await final_polish(winner, budget_tier)

        # Generate feasibility report
        report = await generate_feasibility_report(
            winner=winner,
            budget_tier=budget_tier,
            runner_ups=final_ranked[1:3] if len(final_ranked) > 1 else None
        )

        # Format report as markdown
        report_markdown = format_report_as_markdown(report, winner)

        # Get runner-ups
        runner_ups = final_ranked[1:GENERATION_CONFIG["final_top_ideas"]]

        # =================================================================
        # COMPLETE
        # =================================================================
        await update_job_status(job_id, "complete", 100, "Generation complete!")

        # Store final results
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = {
            "job_id": job_id,
            "topic_used": topic,
            "topic_discovered": topic_result["was_discovered"],
            "budget_tier": budget_tier,
            "total_ideas_generated": jobs[job_id]["ideas_generated"],
            "ideas_after_screening": jobs[job_id].get("ideas_after_screening", 0),
            "ideas_after_stress_test": jobs[job_id].get("ideas_after_stress_test", 0),
            "refinement_rounds": refinement_stats["iterations"],
            "convergence_reason": refinement_stats.get("convergence_reason", ""),
            "winner": {
                "title": winner.idea.title,
                "description": winner.idea.description,
                "problem_solved": winner.idea.problem_solved,
                "target_customer": winner.idea.target_customer,
                "revenue_model": winner.idea.revenue_model,
                "social_impact": winner.idea.social_impact,
                "score": winner.weighted_score,
                "rank": winner.rank
            },
            "runner_ups": [
                {
                    "title": r.idea.title,
                    "description": r.idea.description,
                    "score": r.weighted_score,
                    "rank": r.rank
                }
                for r in runner_ups
            ],
            "feasibility_report": report.model_dump(),
            "report_markdown": report_markdown,
            "ranking_insights": get_ranking_insights(final_ranked),
            "evaluation_stats": eval_stats,
            "refinement_stats": refinement_stats
        }

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        print(f"Job {job_id} failed: {e}")


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """Health check and API info."""
    return {
        "name": "Idea Generator",
        "version": "2.0.0",
        "description": "AI-powered startup idea generation and validation",
        "endpoints": {
            "POST /generate": "Start idea generation",
            "GET /status/{job_id}": "Check job status",
            "GET /results/{job_id}": "Get final results",
            "GET /judges": "List all judges",
            "GET /budget-tiers": "List budget tiers"
        }
    }


@app.post("/generate")
async def generate(
    request: GenerationRequest,
    background_tasks: BackgroundTasks
):
    """
    Start the idea generation pipeline.

    This is an async operation. Use /status/{job_id} to track progress
    and /results/{job_id} to get final results.
    """
    job_id = str(uuid.uuid4())

    # Initialize job
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "phase": "initializing",
        "progress": 0,
        "current_action": "Starting...",
        "request": request.model_dump(),
        "ideas_generated": 0,
        "ideas_evaluated": 0,
        "refinement_rounds": 0,
        "errors": []
    }

    # Start background task
    background_tasks.add_task(run_generation_pipeline, job_id, request)

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Idea generation started. Use /status/{job_id} to track progress."
    }


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Get the current status of a generation job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return {
        "job_id": job_id,
        "status": job.get("status", "unknown"),
        "phase": job.get("phase", ""),
        "progress": job.get("progress", 0),
        "current_action": job.get("current_action", ""),
        "ideas_generated": job.get("ideas_generated", 0),
        "ideas_evaluated": job.get("ideas_evaluated", 0),
        "refinement_rounds": job.get("refinement_rounds", 0),
        "error": job.get("error") if job.get("status") == "failed" else None
    }


@app.get("/results/{job_id}")
async def get_results(job_id: str):
    """Get the final results of a completed generation job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    if job.get("status") == "failed":
        raise HTTPException(status_code=500, detail=job.get("error", "Job failed"))

    if job.get("status") != "completed":
        raise HTTPException(
            status_code=202,
            detail=f"Job still in progress. Phase: {job.get('phase')}. Progress: {job.get('progress')}%"
        )

    return job.get("result", {})


@app.get("/results/{job_id}/report")
async def get_report_markdown(job_id: str):
    """Get just the markdown feasibility report."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    if job.get("status") != "completed":
        raise HTTPException(status_code=202, detail="Job not yet completed")

    result = job.get("result", {})
    return {
        "report": result.get("report_markdown", "No report available")
    }


@app.get("/judges")
async def list_judges():
    """Get information about all judge personas."""
    return {
        "judges": get_all_judges_info(),
        "total": len(get_all_judges_info())
    }


@app.get("/budget-tiers")
async def list_budget_tiers():
    """Get all available budget tiers and their constraints."""
    return {
        "tiers": {
            name: {
                "range": f"${config['range'][0]:,} - ${config['range'][1]:,}" if config['range'][1] != float('inf') else f"${config['range'][0]:,}+",
                "constraints": config["constraints"],
                "team_size": config["team_size"]
            }
            for name, config in BUDGET_TIERS.items()
        }
    }


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its results."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    del jobs[job_id]
    return {"message": f"Job {job_id} deleted"}


# =============================================================================
# SIMPLE SYNC ENDPOINT (for quick tests)
# =============================================================================

@app.post("/quick-generate")
async def quick_generate(
    topic: str = "sustainable technology",
    budget: str = "bootstrapped",
    count: int = 10
):
    """
    Quick synchronous generation for testing.
    Generates fewer ideas and skips refinement loop.
    """
    try:
        budget_tier, budget_config = await parse_budget(budget)

        # Generate ideas
        ideas = await generate_all_ideas(
            topic=topic,
            budget_tier=budget_tier,
            budget_config=budget_config,
            total_ideas=count,
            ideas_per_batch=count
        )

        # Quick evaluation (no stress test, fewer judges)
        from evaluation.evaluator import quick_evaluate_for_ranking

        evaluated = await quick_evaluate_for_ranking(ideas[:10], budget_tier)
        ranked = rank_ideas(evaluated)

        return {
            "topic": topic,
            "budget_tier": budget_tier,
            "ideas_generated": len(ideas),
            "top_ideas": [
                {
                    "rank": i.rank,
                    "title": i.idea.title,
                    "description": i.idea.description,
                    "score": i.weighted_score
                }
                for i in ranked[:5]
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
