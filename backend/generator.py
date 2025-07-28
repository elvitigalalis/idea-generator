import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key = os.getenv("GEMINI_API_KEY"))

def generate_ideas(seed: str = "", count: int = 10) -> list[str]:
  model_input = "gemini-2.5-flash"
  contents_input = f"Generate {count} creative, unique startup ideas based on: {seed}"
  response = client.models.generate_content(
    model = model_input,
    contents = contents_input)
  ideas = response.text.split("\n")
  return ideas