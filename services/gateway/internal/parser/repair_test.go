package parser

import (
	"context"
	"errors"
	"testing"

	"idea-evolution-engine/services/gateway/internal/schema"
)

func TestPureGoRepairParserParsesValidJSON(t *testing.T) {
	p := NewPureGoRepairParser()
	raw := []byte(`{"concept_name":"Valid Idea","estimated_startup_cost":1200,"feasibility_score":0.8,"risk_factors":["cost"],"marketing_angle":"Simple angle"}`)

	idea, err := p.ParseIdea(context.Background(), &raw)
	if err != nil {
		t.Fatalf("ParseIdea returned error: %v", err)
	}
	if idea.ConceptName != "Valid Idea" {
		t.Fatalf("unexpected concept name: %q", idea.ConceptName)
	}
}

func TestPureGoRepairParserRepairsPreambleTrailingCommaAndMissingBrace(t *testing.T) {
	p := NewPureGoRepairParser()
	raw := []byte(`Here is JSON:
{"concept_name":"Repaired Idea","estimated_startup_cost":2500,"feasibility_score":0.9,"risk_factors":["market risk",],"marketing_angle":"Local launch"`)

	idea, err := p.ParseIdea(context.Background(), &raw)
	if err != nil {
		t.Fatalf("ParseIdea returned error: %v", err)
	}
	if idea.ConceptName != "Repaired Idea" {
		t.Fatalf("unexpected concept name: %q", idea.ConceptName)
	}
	if len(idea.RiskFactors) != 1 || idea.RiskFactors[0] != "market risk" {
		t.Fatalf("unexpected risk factors: %#v", idea.RiskFactors)
	}
}

func TestPureGoRepairParserRepairsMarkdownArray(t *testing.T) {
	p := NewPureGoRepairParser()
	raw := []byte("```json\n[{\"concept_name\":\"Array Idea\",\"estimated_startup_cost\":4000,\"feasibility_score\":0.82,\"risk_factors\":[\"ops\"],\"marketing_angle\":\"Niche offer\",}]\n```")

	var ideas []schema.BusinessIdea
	parsed, err := p.ParseIdeas(context.Background(), &raw, &ideas)
	if err != nil {
		t.Fatalf("ParseIdeas returned error: %v", err)
	}
	if len(parsed) != 1 || parsed[0].ConceptName != "Array Idea" {
		t.Fatalf("unexpected parsed ideas: %#v", parsed)
	}
}

func TestPureGoRepairParserReturnsClearErrorForUnrecoverablePayload(t *testing.T) {
	p := NewPureGoRepairParser()
	raw := []byte(`there is no structured payload here`)

	_, err := p.ParseIdea(context.Background(), &raw)
	if !errors.Is(err, ErrNoJSONFound) {
		t.Fatalf("expected ErrNoJSONFound, got %v", err)
	}
}
