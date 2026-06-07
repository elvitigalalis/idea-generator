package main

import (
	"context"
	"math"
	"strings"
	"testing"

	"idea-evolution-engine/services/gateway/internal/parser"
	"idea-evolution-engine/services/gateway/internal/schema"

	"google.golang.org/genai"
)

func TestBusinessIdeaSchemaUsesTypedConstants(t *testing.T) {
	s := businessIdeaSchema()
	if s.Type != genai.TypeObject {
		t.Fatalf("schema type = %v, want %v", s.Type, genai.TypeObject)
	}
	if s.Properties["concept_name"].Type != genai.TypeString {
		t.Fatalf("concept_name type = %v, want %v", s.Properties["concept_name"].Type, genai.TypeString)
	}
	if s.Properties["estimated_startup_cost"].Type != genai.TypeNumber {
		t.Fatalf("estimated_startup_cost type = %v, want %v", s.Properties["estimated_startup_cost"].Type, genai.TypeNumber)
	}
	if s.Properties["feasibility_score"].Type != genai.TypeInteger {
		t.Fatalf("feasibility_score type = %v, want %v", s.Properties["feasibility_score"].Type, genai.TypeInteger)
	}
	if len(s.Required) != 5 {
		t.Fatalf("required fields = %d, want 5", len(s.Required))
	}
}

func TestGeminiDTOConvertsRiskStringToSlice(t *testing.T) {
	dto := geminiIdeaDTO{
		ConceptName:          "Local Ops AI",
		EstimatedStartupCost: 5000,
		FeasibilityScore:     87,
		RiskFactors:          "customer education",
		MarketingAngle:       "fast local automation",
	}

	idea := dto.toBusinessIdea()
	if len(idea.RiskFactors) != 1 || idea.RiskFactors[0] != "customer education" {
		t.Fatalf("risk factors = %#v, want one normalized string", idea.RiskFactors)
	}
}

func TestParseBusinessIdeaStrictPath(t *testing.T) {
	raw := []byte(`{"concept_name":"Strict Idea","estimated_startup_cost":1200,"feasibility_score":91,"risk_factors":"pricing pressure","marketing_angle":"clear local value"}`)

	idea, healed, err := parseBusinessIdea(context.Background(), raw, parser.NewPureGoRepairParser())
	if err != nil {
		t.Fatalf("parseBusinessIdea returned error: %v", err)
	}
	if healed {
		t.Fatal("strict JSON should not require healing")
	}
	if idea.ConceptName != "Strict Idea" || len(idea.RiskFactors) != 1 {
		t.Fatalf("unexpected idea: %#v", idea)
	}
}

func TestParseBusinessIdeaFallbackPath(t *testing.T) {
	raw := []byte("```json\n{\"concept_name\":\"Healed Idea\",\"estimated_startup_cost\":2200,\"feasibility_score\":82,\"risk_factors\":[\"ops risk\",],\"marketing_angle\":\"better local ops\"\n```")

	idea, healed, err := parseBusinessIdea(context.Background(), raw, parser.NewPureGoRepairParser())
	if err != nil {
		t.Fatalf("parseBusinessIdea returned error: %v", err)
	}
	if !healed {
		t.Fatal("malformed JSON should require healing")
	}
	if idea.ConceptName != "Healed Idea" {
		t.Fatalf("unexpected idea: %#v", idea)
	}
}

func TestAggregateIdeasUsesNativeRanking(t *testing.T) {
	ideas := []schema.BusinessIdea{
		{FeasibilityScore: 80},
		{FeasibilityScore: 90},
		{FeasibilityScore: 100},
	}

	aggregate, average := aggregateIdeas(ideas)
	if math.Abs(float64(aggregate-270)) > 0.001 {
		t.Fatalf("aggregate = %v, want 270", aggregate)
	}
	if math.Abs(float64(average-90)) > 0.001 {
		t.Fatalf("average = %v, want 90", average)
	}
}

func TestRunLiveWorkerSafelyRecoversPanic(t *testing.T) {
	out := make(chan liveWorkerResult, 1)
	srv := &server{}

	srv.runLiveWorkerSafely(context.Background(), 7, schema.EvolutionRequest{}, out)

	result := <-out
	if result.Err == nil {
		t.Fatal("expected recovered panic error")
	}
	if !strings.Contains(result.Err.Error(), "worker 7 panic") {
		t.Fatalf("unexpected error: %v", result.Err)
	}
}
