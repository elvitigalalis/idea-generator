package coordinator

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

	"idea-evolution-engine/services/gateway/internal/parser"
	"idea-evolution-engine/services/gateway/internal/schema"
)

func TestCoordinatorReturnsAfterQuorum(t *testing.T) {
	c := New(parser.NewPureGoRepairParser(), NewTokenBucket(4, time.Millisecond), Config{
		WorkerCount: 4,
		Quorum:      3,
		Timeout:     1200 * time.Millisecond,
	})
	defer c.limiter.Close()

	resp, err := c.Evolve(context.Background(), validRequest())
	if err != nil {
		t.Fatalf("Evolve returned error: %v", err)
	}
	if resp.SuccessfulWorkers != 3 {
		t.Fatalf("expected 3 successful workers, got %d", resp.SuccessfulWorkers)
	}
	if !resp.ReturnedEarly {
		t.Fatal("expected returned_early to be true")
	}
	if resp.ElapsedMS >= 1000 {
		t.Fatalf("expected quorum response before stalled worker, elapsed=%dms", resp.ElapsedMS)
	}
}

func TestCoordinatorReturnsPartialSuccessOnTimeout(t *testing.T) {
	c := New(parser.NewPureGoRepairParser(), NewTokenBucket(4, time.Millisecond), Config{
		WorkerCount: 4,
		Quorum:      4,
		Timeout:     300 * time.Millisecond,
	})
	defer c.limiter.Close()

	resp, err := c.Evolve(context.Background(), validRequest())
	if err != nil {
		t.Fatalf("Evolve returned error: %v", err)
	}
	if resp.SuccessfulWorkers != 3 {
		t.Fatalf("expected 3 partial successes, got %d", resp.SuccessfulWorkers)
	}
	if resp.FailedWorkers != 1 {
		t.Fatalf("expected 1 failed worker, got %d", resp.FailedWorkers)
	}
	if resp.ReturnedEarly {
		t.Fatal("timeout partial response should not be marked returned_early")
	}
}

func TestCoordinatorFailsWhenNoIdeasRecovered(t *testing.T) {
	c := New(failingParser{}, NewTokenBucket(4, time.Millisecond), Config{
		WorkerCount: 1,
		Quorum:      1,
		Timeout:     250 * time.Millisecond,
	})
	defer c.limiter.Close()

	_, err := c.Evolve(context.Background(), validRequest())
	if err == nil || !strings.Contains(err.Error(), "all workers failed") {
		t.Fatalf("expected all workers failed error, got %v", err)
	}
}

func TestCoordinatorResetsPooledIdeaSlices(t *testing.T) {
	c := New(parser.NewPureGoRepairParser(), NewTokenBucket(4, time.Millisecond), Config{
		WorkerCount: 4,
		Quorum:      3,
		Timeout:     1200 * time.Millisecond,
	})
	defer c.limiter.Close()

	first, err := c.Evolve(context.Background(), validRequest())
	if err != nil {
		t.Fatalf("first Evolve returned error: %v", err)
	}
	second, err := c.Evolve(context.Background(), validRequest())
	if err != nil {
		t.Fatalf("second Evolve returned error: %v", err)
	}
	if len(first.Ideas) != 3 || len(second.Ideas) != 3 {
		t.Fatalf("expected pooled slice reset between calls, got %d then %d", len(first.Ideas), len(second.Ideas))
	}
}

type failingParser struct{}

func (failingParser) ParseIdea(context.Context, *[]byte) (schema.BusinessIdea, error) {
	return schema.BusinessIdea{}, errors.New("forced parser failure")
}

func (failingParser) ParseIdeas(context.Context, *[]byte, *[]schema.BusinessIdea) ([]schema.BusinessIdea, error) {
	return nil, errors.New("forced parser failure")
}

func validRequest() schema.EvolutionRequest {
	return schema.EvolutionRequest{
		Budget:       25000,
		Location:     "Austin, TX",
		TargetSector: "AI tools for small businesses",
		Generations:  3,
		SeedCount:    4,
	}
}
