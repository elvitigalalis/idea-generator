"""
Test script for the Idea Generator system.

Run this to test the system end-to-end.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Verify API key
if not os.getenv("GEMINI_API_KEY"):
    print("ERROR: GEMINI_API_KEY not found in environment!")
    print("Create a .env file with: GEMINI_API_KEY=your_key_here")
    sys.exit(1)

print("✓ API key found")


async def test_gemini_connection():
    """Test basic Gemini API connection."""
    print("\n=== Testing Gemini Connection ===")
    from utils.gemini_client import generate_content

    try:
        response = await generate_content("Say 'Hello' in one word", temperature=0.1)
        print(f"✓ Gemini API working: {response.strip()[:50]}")
        return True
    except Exception as e:
        print(f"✗ Gemini API error: {e}")
        return False


async def test_niche_discovery():
    """Test niche discovery."""
    print("\n=== Testing Niche Discovery ===")
    from discovery.niche_finder import parse_budget, discover_niche

    try:
        # Test budget parsing
        tier, config = await parse_budget("$5000")
        print(f"✓ Budget parsing: $5000 → {tier}")

        tier2, _ = await parse_budget("bootstrapped")
        print(f"✓ Budget parsing: bootstrapped → {tier2}")

        # Test niche discovery
        print("  Discovering niches (this may take 10-15 seconds)...")
        niches = await discover_niche("minimal", "any", "general")
        print(f"✓ Discovered {len(niches.get('niches', []))} niches")
        if niches.get('recommended_niche'):
            print(f"  Recommended: {niches['recommended_niche']}")
        return True
    except Exception as e:
        print(f"✗ Niche discovery error: {e}")
        return False


async def test_idea_generation():
    """Test idea generation (small batch)."""
    print("\n=== Testing Idea Generation ===")
    from generation.idea_generator import generate_idea_batch
    from config import BUDGET_TIERS

    try:
        print("  Generating 5 ideas (this may take 15-20 seconds)...")
        ideas = await generate_idea_batch(
            topic="sustainable technology",
            budget_tier="bootstrapped",
            budget_config=BUDGET_TIERS["bootstrapped"],
            batch_number=0,
            count=5
        )
        print(f"✓ Generated {len(ideas)} ideas")
        for i, idea in enumerate(ideas[:3], 1):
            print(f"  {i}. {idea.title}")
        return ideas
    except Exception as e:
        print(f"✗ Idea generation error: {e}")
        return None


async def test_screening(ideas):
    """Test idea screening."""
    print("\n=== Testing Screening ===")
    from evaluation.screener import quick_screen_idea

    try:
        if not ideas:
            print("  Skipping (no ideas to screen)")
            return None

        print("  Screening first idea...")
        result = await quick_screen_idea(ideas[0], "bootstrapped")
        print(f"✓ Screening complete")
        print(f"  Passes: {result.get('final_pass')}")
        print(f"  Scores: {result.get('scores')}")
        return result
    except Exception as e:
        print(f"✗ Screening error: {e}")
        return None


async def test_judge_evaluation(ideas):
    """Test judge evaluation."""
    print("\n=== Testing Judge Evaluation ===")
    from evaluation.judges import get_judge_evaluation, JUDGES

    try:
        if not ideas:
            print("  Skipping (no ideas to evaluate)")
            return None

        print("  Getting evaluation from 'The VC' judge...")
        judge = JUDGES["vc"]
        result = await get_judge_evaluation(ideas[0], judge, "bootstrapped")
        print(f"✓ Judge evaluation complete")
        print(f"  Overall score: {result.overall_score}/10")
        print(f"  Key insight: {result.key_insight[:100]}...")
        return result
    except Exception as e:
        print(f"✗ Judge evaluation error: {e}")
        return None


async def test_stress_test(ideas):
    """Test the 99% killer stress test."""
    print("\n=== Testing Stress Test (99% Killer) ===")
    from evaluation.stress_test import stress_test_idea

    try:
        if not ideas:
            print("  Skipping (no ideas to stress test)")
            return None

        print("  Running stress test on first idea...")
        result = await stress_test_idea(ideas[0], "bootstrapped")
        print(f"✓ Stress test complete")
        print(f"  Survival score: {result.survival_score}/10")
        print(f"  Recommendation: {result.recommendation}")
        print(f"  Flaws found: {result.flaw_count}")
        if result.fundamental_flaws:
            print(f"  Top flaw: {result.fundamental_flaws[0][:80]}...")
        return result
    except Exception as e:
        print(f"✗ Stress test error: {e}")
        return None


async def test_full_quick_flow():
    """Test the quick generation endpoint logic."""
    print("\n=== Testing Quick Generation Flow ===")
    from discovery.niche_finder import parse_budget
    from generation.idea_generator import generate_all_ideas
    from evaluation.evaluator import quick_evaluate_for_ranking
    from ranking.ranker import rank_ideas
    from config import BUDGET_TIERS

    try:
        budget_tier, budget_config = await parse_budget("bootstrapped")

        print("  Generating 10 ideas...")
        ideas = await generate_all_ideas(
            topic="AI productivity tools",
            budget_tier=budget_tier,
            budget_config=budget_config,
            total_ideas=10,
            ideas_per_batch=10
        )
        print(f"  Generated {len(ideas)} ideas")

        print("  Quick evaluating top 5...")
        evaluated = await quick_evaluate_for_ranking(ideas[:5], budget_tier)

        print("  Ranking...")
        ranked = rank_ideas(evaluated)

        print(f"✓ Quick flow complete!")
        print("\n  TOP 3 IDEAS:")
        for idea in ranked[:3]:
            print(f"  #{idea.rank} ({idea.weighted_score:.1f}/10): {idea.idea.title}")
            print(f"      {idea.idea.description[:100]}...")
            print()

        return True
    except Exception as e:
        print(f"✗ Quick flow error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("IDEA GENERATOR - TEST SUITE")
    print("=" * 60)

    results = {}

    # Test 1: Gemini connection
    results["gemini"] = await test_gemini_connection()
    if not results["gemini"]:
        print("\n⚠ Cannot continue without Gemini API connection")
        return

    # Test 2: Niche discovery
    results["niche"] = await test_niche_discovery()

    # Test 3: Idea generation
    ideas = await test_idea_generation()
    results["generation"] = ideas is not None

    # Test 4: Screening
    results["screening"] = await test_screening(ideas) is not None

    # Test 5: Judge evaluation
    results["judge"] = await test_judge_evaluation(ideas) is not None

    # Test 6: Stress test
    results["stress"] = await test_stress_test(ideas) is not None

    # Test 7: Full quick flow
    results["full_flow"] = await test_full_quick_flow()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test, passed_test in results.items():
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"  {test}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! The system is ready to use.")
        print("\nTo run the full server:")
        print("  cd backend && uvicorn main:app --reload")
    else:
        print("\n⚠ Some tests failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())
