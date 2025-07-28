def rank_ideas(evaluated: list[dict]) -> list[dict]:
  def score(s):
    return (
      0.4 * s["market"]["score"] + 0.3 * s["novelty"]["score"] + 0.3 * s["feasibility"]["score"]
    )
  return sorted(evaluated, key=lambda x: score(x["scores"]), reverse=True)[:5]