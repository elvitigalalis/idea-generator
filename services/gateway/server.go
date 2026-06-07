package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"time"

	"idea-evolution-engine/services/gateway/internal/coordinator"
	"idea-evolution-engine/services/gateway/internal/parser"
	"idea-evolution-engine/services/gateway/internal/schema"

	"google.golang.org/genai"
)

type server struct {
	coordinator *coordinator.Coordinator
	client      *genai.Client
	limiter     *coordinator.TokenBucket
	parser      parser.IdeaParser
}

func (s *server) handleEvolve(w http.ResponseWriter, r *http.Request) {
	var req schema.EvolutionRequest
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	if err := dec.Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request json: "+err.Error())
		return
	}

	resp, err := s.coordinator.Evolve(r.Context(), req)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, resp)
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(payload); err != nil {
		log.Printf("encode response: %v", err)
	}
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}

func (s *server) handleLiveEvolve(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	var req schema.EvolutionRequest
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	if err := dec.Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid request json: "+err.Error())
		return
	}
	if err := validateLiveRequest(req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	resp, err := s.evolveWithGemini(r.Context(), req)
	if err != nil {
		writeError(w, http.StatusBadGateway, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, resp)
}

func (s *server) evolveWithGemini(parent context.Context, req schema.EvolutionRequest) (schema.EvolutionResponse, error) {
	start := time.Now()
	ctx, cancel := context.WithTimeout(parent, liveTimeout)
	defer cancel()

	results := make(chan liveWorkerResult, liveWorkerCount)
	for workerID := 0; workerID < liveWorkerCount; workerID++ {
		go s.runLiveWorkerSafely(ctx, workerID, req, results)
	}

	ideas := make([]schema.BusinessIdea, 0, liveQuorum)
	errorsOut := make([]string, 0)
	failed := 0
	received := 0
	returnedEarly := false

	for received < liveWorkerCount {
		select {
		case result := <-results:
			received++
			if result.Err != nil {
				failed++
				msg := fmt.Sprintf("worker %d: %v", result.WorkerID, result.Err)
				errorsOut = append(errorsOut, msg)
				log.Printf("live worker %d failed: %v", result.WorkerID, result.Err)
				continue
			}

			ideas = append(ideas, result.Idea)
			if result.Healed {
				log.Printf("live worker %d parsed via local defensive repair", result.WorkerID)
			} else {
				log.Printf("live worker %d parsed directly from structured output", result.WorkerID)
			}

			if len(ideas) >= liveQuorum {
				returnedEarly = true
				cancel()
				aggregate, average := aggregateIdeas(ideas)
				return schema.EvolutionResponse{
					Ideas:                   ideas,
					SuccessfulWorkers:       len(ideas),
					FailedWorkers:           failed,
					ReturnedEarly:           returnedEarly,
					ElapsedMS:               time.Since(start).Milliseconds(),
					AggregateScore:          aggregate,
					AverageFeasibilityScore: average,
					Errors:                  errorsOut,
				}, nil
			}
		case <-ctx.Done():
			failed += liveWorkerCount - received
			if len(ideas) == 0 {
				return schema.EvolutionResponse{}, fmt.Errorf("no live Gemini ideas recovered before timeout: %w", ctx.Err())
			}
			errorsOut = append(errorsOut, ctx.Err().Error())
			aggregate, average := aggregateIdeas(ideas)
			return schema.EvolutionResponse{
				Ideas:                   ideas,
				SuccessfulWorkers:       len(ideas),
				FailedWorkers:           failed,
				ReturnedEarly:           false,
				ElapsedMS:               time.Since(start).Milliseconds(),
				AggregateScore:          aggregate,
				AverageFeasibilityScore: average,
				Errors:                  errorsOut,
			}, nil
		}
	}

	if len(ideas) == 0 {
		return schema.EvolutionResponse{}, errors.New("all live Gemini workers failed")
	}

	aggregate, average := aggregateIdeas(ideas)
	return schema.EvolutionResponse{
		Ideas:                   ideas,
		SuccessfulWorkers:       len(ideas),
		FailedWorkers:           failed,
		ReturnedEarly:           returnedEarly,
		ElapsedMS:               time.Since(start).Milliseconds(),
		AggregateScore:          aggregate,
		AverageFeasibilityScore: average,
		Errors:                  errorsOut,
	}, nil
}

func (s *server) runLiveWorkerSafely(ctx context.Context, workerID int, req schema.EvolutionRequest, out chan<- liveWorkerResult) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err := fmt.Errorf("worker %d panic: %v", workerID, recovered)
			log.Printf("live worker %d recovered panic: %v", workerID, recovered)
			s.emitLiveResult(ctx, out, liveWorkerResult{WorkerID: workerID, Err: err})
		}
	}()

	s.runLiveWorker(ctx, workerID, req, out)
}

func (s *server) runLiveWorker(ctx context.Context, workerID int, req schema.EvolutionRequest, out chan<- liveWorkerResult) {
	log.Printf("live worker %d queued by Gemini rate limiter", workerID)
	if err := s.limiter.Acquire(ctx); err != nil {
		s.emitLiveResult(ctx, out, liveWorkerResult{WorkerID: workerID, Err: err})
		return
	}
	log.Printf("live worker %d acquired Gemini rate limiter token", workerID)

	prompt := buildLivePrompt(req, workerID)
	resp, err := s.client.Models.GenerateContent(
		ctx,
		geminiModel,
		genai.Text(prompt),
		liveGenerateConfig(),
	)
	if err != nil {
		s.emitLiveResult(ctx, out, liveWorkerResult{WorkerID: workerID, Err: err})
		return
	}

	rawText := resp.Text()
	log.Printf("live worker %d raw Gemini response: %s", workerID, rawText)
	raw := []byte(rawText)

	idea, healed, err := parseBusinessIdea(ctx, raw, s.parser)
	s.emitLiveResult(ctx, out, liveWorkerResult{
		WorkerID: workerID,
		Idea:     idea,
		Err:      err,
		Healed:   healed,
	})
}

func (s *server) emitLiveResult(ctx context.Context, out chan<- liveWorkerResult, result liveWorkerResult) {
	select {
	case out <- result:
	case <-ctx.Done():
	}
}

func validateLiveRequest(req schema.EvolutionRequest) error {
	if req.Budget <= 0 {
		return errors.New("budget must be greater than zero")
	}
	if req.Location == "" {
		return errors.New("location is required")
	}
	if req.TargetSector == "" {
		return errors.New("target_sector is required")
	}
	if req.Generations <= 0 {
		return errors.New("generations must be greater than zero")
	}
	if req.SeedCount <= 0 {
		return errors.New("seed_count must be greater than zero")
	}
	return nil
}
