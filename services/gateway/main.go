package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
	"unsafe"

	"idea-evolution-engine/services/gateway/internal/coordinator"
	"idea-evolution-engine/services/gateway/internal/parser"
	"idea-evolution-engine/services/gateway/internal/ranking"
	"idea-evolution-engine/services/gateway/internal/schema"

	"google.golang.org/genai"
)

const (
	geminiModel     = "gemini-2.5-flash"
	liveWorkerCount = 4
	liveQuorum      = 3
	liveTimeout     = 15 * time.Second
)

func main() {
	apiKey := os.Getenv("GEMINI_API_KEY")
	if apiKey == "" {
		apiKey = os.Getenv("GOOGLE_API_KEY")
	}
	if apiKey == "" {
		log.Fatal("FATAL: Neither GEMINI_API_KEY nor GOOGLE_API_KEY environment variable is set.")
	}

	ctx := context.Background()
	client, err := genai.NewClient(ctx, nil)
	if err != nil {
		log.Fatalf("FATAL: Failed to initialize GenAI client: %v", err)
	}

	limiter := coordinator.NewTokenBucket(3, 500*time.Millisecond)
	defer limiter.Close()

	srv := &server{
		client:  client,
		limiter: limiter,
		parser:  parser.NewPureGoRepairParser(),
	}

	mux := http.NewServeMux()
	mux.HandleFunc("POST /evolve", srv.handleLiveEvolve)
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNoContent)
	})

	log.Println("Live Gemini API Gateway running on http://localhost:8080")
	if err := http.ListenAndServe(":8080", mux); err != nil {
		log.Fatal(err)
	}
}

type geminiIdeaDTO struct {
	ConceptName          string  `json:"concept_name"`
	EstimatedStartupCost float64 `json:"estimated_startup_cost"`
	FeasibilityScore     float64 `json:"feasibility_score"`
	RiskFactors          string  `json:"risk_factors"`
	MarketingAngle       string  `json:"marketing_angle"`
}

type liveWorkerResult struct {
	WorkerID int
	Idea     schema.BusinessIdea
	Err      error
	Healed   bool
}

func businessIdeaSchema() *genai.Schema {
	return &genai.Schema{
		Type: genai.TypeObject,
		Properties: map[string]*genai.Schema{
			"concept_name": {
				Type:        genai.TypeString,
				Description: "The name of the business concept.",
			},
			"estimated_startup_cost": {
				Type:        genai.TypeNumber,
				Description: "Estimated initial capital required in USD.",
			},
			"feasibility_score": {
				Type:        genai.TypeInteger,
				Description: "Numerical feasibility score from 1 to 100.",
			},
			"risk_factors": {
				Type:        genai.TypeString,
				Description: "Primary risks associated with execution.",
			},
			"marketing_angle": {
				Type:        genai.TypeString,
				Description: "The core value proposition or marketing hook.",
			},
		},
		Required: []string{
			"concept_name",
			"estimated_startup_cost",
			"feasibility_score",
			"risk_factors",
			"marketing_angle",
		},
	}
}

func liveGenerateConfig() *genai.GenerateContentConfig {
	return &genai.GenerateContentConfig{
		ResponseMIMEType: "application/json",
		ResponseSchema:   businessIdeaSchema(),
		Temperature:      genai.Ptr(float32(0.1)),
	}
}

func buildLivePrompt(req schema.EvolutionRequest, workerID int) string {
	return fmt.Sprintf(
		"Generate one distinct business idea for target sector %q in %s with startup budget %.2f USD. "+
			"This is worker %d of %d for generation depth %d and seed count %d. "+
			"Return only JSON matching the response schema. Keep feasibility_score as an integer from 1 to 100 and risk_factors as one concise string.",
		req.TargetSector,
		req.Location,
		req.Budget,
		workerID+1,
		liveWorkerCount,
		req.Generations,
		req.SeedCount,
	)
}

func parseBusinessIdea(ctx context.Context, raw []byte, repairParser parser.IdeaParser) (schema.BusinessIdea, bool, error) {
	var dto geminiIdeaDTO
	if err := json.Unmarshal(raw, &dto); err == nil && dto.ConceptName != "" {
		return dto.toBusinessIdea(), false, nil
	}

	idea, err := repairParser.ParseIdea(ctx, &raw)
	if err != nil {
		return schema.BusinessIdea{}, true, err
	}
	return idea, true, nil
}

func (g geminiIdeaDTO) toBusinessIdea() schema.BusinessIdea {
	return schema.BusinessIdea{
		ConceptName:          g.ConceptName,
		EstimatedStartupCost: g.EstimatedStartupCost,
		FeasibilityScore:     g.FeasibilityScore,
		RiskFactors:          []string{g.RiskFactors},
		MarketingAngle:       g.MarketingAngle,
	}
}

func aggregateIdeas(ideas []schema.BusinessIdea) (float32, float32) {
	if len(ideas) == 0 {
		return 0, 0
	}

	flatScores := make([]float32, len(ideas))
	for i, idea := range ideas {
		flatScores[i] = float32(idea.FeasibilityScore)
	}

	log.Printf("ranking: passing %d feasibility scores to C++ at pointer=%p", len(flatScores), unsafe.SliceData(flatScores))
	aggregateScore := ranking.RankIdeas(flatScores)
	averageScore := aggregateScore / float32(len(flatScores))
	log.Printf("ranking: aggregate_score=%.4f average_feasibility_score=%.4f", aggregateScore, averageScore)
	return aggregateScore, averageScore
}
