# Idea Generator

An AI-powered startup idea generation and validation system that produces 100+ ideas, filters them through diverse expert "judges" (Shark Tank style), stress tests them to find the 1% diamonds, and iteratively refines until a winning concept emerges with full business feasibility analysis.

## Features

### Core Capabilities

- **Niche Discovery**: Automatically finds promising niches if no topic provided
- **Mass Idea Generation**: Generates 100+ unique startup ideas in batches
- **Budget-Aware**: Tailors ideas to your specific budget constraints (bootstrapped to venture-scale)
- **Social Entrepreneurship Lens**: Evaluates through Triple Bottom Line (People, Planet, Profit)

### Expert Judge Panel

Six diverse AI personas evaluate every idea:

| Judge | Focus | Weight |
|-------|-------|--------|
| **Victoria Chen** (VC) | ROI, scalability, exit potential | 20% |
| **Marcus Johnson** (Operator) | Execution, operations, team needs | 20% |
| **Dr. Amara Okonkwo** (Impact Investor) | Social impact, sustainability | 20% |
| **Sarah Martinez** (Market Validator) | Customer demand, willingness to pay | 20% |
| **Raj Patel** (Tech Realist) | Technical feasibility, build complexity | 10% |
| **Diana Wolf** (Devil's Advocate) | Risks, failure modes, hidden challenges | 10% |

### The 99% Killer (Stress Test)

Most startup ideas are fundamentally flawed. Our stress test ruthlessly asks:
- Is this solving a REAL problem?
- Would people ACTUALLY pay (not just say they would)?
- Has this been tried and failed? Why?
- What's the simplest reason this wouldn't work?
- Could there be a 10x simpler approach?

Only the 1% diamonds survive to refinement.

### Iterative Refinement Loop

Top 10 ideas enter a refinement cycle:
1. Judges provide detailed feedback
2. Ideas are refined based on feedback
3. Re-evaluated by judges
4. Repeat until convergence or quality threshold met

### Comprehensive Feasibility Report

For the winning idea, generates:
- Executive Summary
- Market Analysis (TAM/SAM/SOM)
- Social Impact Assessment
- Revenue Model & Unit Economics
- Competitive Landscape
- Technical Requirements
- Risk Assessment
- Go-to-Market Strategy
- 90-Day Action Plan

## Quick Start

### Prerequisites

- Python 3.11+
- Google Gemini API key

### Installation

```bash
cd backend
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the backend directory:

```
GEMINI_API_KEY=your_api_key_here
```

### Running

```bash
cd backend
uvicorn main:app --reload
```

Or with Docker:

```bash
docker build -t idea-generator ./backend
docker run -p 8000:8000 -e GEMINI_API_KEY=your_key idea-generator
```

## API Usage

### Start Full Generation

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "sustainable food technology",
    "budget": "$10000",
    "preferences": {
      "business_model": "B2C",
      "impact_focus": "environment"
    }
  }'
```

Response:
```json
{
  "job_id": "abc-123-def",
  "status": "queued",
  "message": "Idea generation started. Use /status/{job_id} to track progress."
}
```

### Check Progress

```bash
curl http://localhost:8000/status/abc-123-def
```

### Get Results

```bash
curl http://localhost:8000/results/abc-123-def
```

### Quick Test (Synchronous)

```bash
curl -X POST "http://localhost:8000/quick-generate?topic=fintech&budget=bootstrapped&count=10"
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check and API info |
| POST | `/generate` | Start full generation pipeline |
| GET | `/status/{job_id}` | Check job progress |
| GET | `/results/{job_id}` | Get final results |
| GET | `/results/{job_id}/report` | Get markdown feasibility report |
| GET | `/judges` | List all judge personas |
| GET | `/budget-tiers` | List available budget tiers |
| POST | `/quick-generate` | Quick synchronous test |
| DELETE | `/jobs/{job_id}` | Delete a job |

## Budget Tiers

| Tier | Range | Constraints |
|------|-------|-------------|
| Bootstrapped | $0-$1K | Solo founder, no-code, organic growth |
| Minimal | $1K-$10K | Small team, limited custom dev |
| Modest | $10K-$50K | Part-time team, custom development |
| Moderate | $50K-$200K | Full-time small team, professional dev |
| Well-Funded | $200K-$1M | Complete team, comprehensive GTM |
| Venture-Scale | $1M+ | No constraints, optimize for growth |

## Project Structure

```
backend/
├── main.py                 # FastAPI app & orchestration
├── config.py               # Configuration & constants
├── models.py               # Pydantic models
├── discovery/
│   └── niche_finder.py     # Niche discovery
├── generation/
│   ├── idea_generator.py   # Idea generation
│   └── idea_refiner.py     # Idea refinement
├── evaluation/
│   ├── judges.py           # Judge personas
│   ├── evaluator.py        # Evaluation orchestration
│   ├── screener.py         # Quick screening
│   └── stress_test.py      # The 99% killer
├── ranking/
│   └── ranker.py           # Weighted ranking
├── refinement/
│   └── refinement_loop.py  # Iterative improvement
├── reporting/
│   └── feasibility.py      # Business reports
└── utils/
    ├── gemini_client.py    # Gemini API client
    └── prompts.py          # Prompt templates
```

## Evaluation Criteria

### Market & Revenue (30%)
- Market size potential
- Revenue clarity
- Pricing power
- Customer acquisition ease

### Social Impact (25%)
- Impact breadth and depth
- Environmental consideration
- Mission sustainability
- Measurability

### Feasibility (25%)
- Technical complexity
- Budget fit
- Time to MVP
- Resource requirements

### Differentiation (20%)
- Uniqueness
- Competitive moat
- Network effects
- Switching costs

## License

MIT License - see LICENSE file

## Contributing

Contributions welcome! Please read the architecture documentation in `ARCHITECTURE.md` first.
