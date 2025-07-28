from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from generator import generate_ideas
from judges import evaluate_ideas
from ranker import rank_ideas

app = FastAPI()
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

@app.post("/evaluate/")
async def evaluate(seed : str) -> list[dict]:
  ideas = generate_ideas(seed, count = 10)
  judged = evaluate_ideas(ideas)
  top = rank_ideas(judged)
  return {"top_ideas": top}