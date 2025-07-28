import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key = os.getenv("GEMINI_API_KEY"))

def judge(idea: str, aspect: str) -> dict:
  model_input = "gemini-2.5-flash"
  contents_input = f"Rate this start up idea on {aspect} from 1-10 and explain briefly: {idea}"
  response = client.models.generate_content(
    model = model_input,
    contents = contents_input
  )
  content = response.text
  # score = int("".join(filter(str.isdigit, content.split()[0])))
  score = 1
  return {"score": score, "reason": content}

def evaluate_ideas(ideas: list[str]) -> list[dict]:
  results = []
  for idea in ideas:
    scores = {
      "market": judge(idea, "market size"),
      "novelty": judge(idea, "novelty"),
      "feasibility": judge(idea, "technical feasibility")
    }
    results.append({"idea": idea, "scores": scores})
  return results