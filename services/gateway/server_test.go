package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"idea-evolution-engine/services/gateway/internal/coordinator"
	"idea-evolution-engine/services/gateway/internal/parser"
	"idea-evolution-engine/services/gateway/internal/schema"
)

func TestHandleEvolveReturnsIdeas(t *testing.T) {
	limiter := coordinator.NewTokenBucket(4, time.Millisecond)
	defer limiter.Close()

	srv := &server{
		coordinator: coordinator.New(parser.NewPureGoRepairParser(), limiter, coordinator.Config{
			WorkerCount: 4,
			Quorum:      3,
			Timeout:     1200 * time.Millisecond,
		}),
	}

	body := strings.NewReader(`{"budget":25000,"location":"Austin, TX","target_sector":"AI tools","generations":3,"seed_count":4}`)
	req := httptest.NewRequest(http.MethodPost, "/evolve", body)
	rec := httptest.NewRecorder()

	srv.handleEvolve(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", rec.Code, rec.Body.String())
	}

	var resp schema.EvolutionResponse
	if err := json.NewDecoder(rec.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.SuccessfulWorkers != 3 || len(resp.Ideas) != 3 {
		t.Fatalf("unexpected response: %#v", resp)
	}
}

func TestHandleEvolveRejectsUnknownFields(t *testing.T) {
	limiter := coordinator.NewTokenBucket(1, time.Millisecond)
	defer limiter.Close()

	srv := &server{
		coordinator: coordinator.New(parser.NewPureGoRepairParser(), limiter, coordinator.Config{}),
	}

	req := httptest.NewRequest(http.MethodPost, "/evolve", bytes.NewBufferString(`{"budget":1,"location":"x","target_sector":"y","generations":1,"seed_count":1,"extra":true}`))
	rec := httptest.NewRecorder()

	srv.handleEvolve(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d", rec.Code)
	}
}
