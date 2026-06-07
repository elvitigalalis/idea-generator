package coordinator

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"idea-evolution-engine/services/gateway/internal/parser"
	"idea-evolution-engine/services/gateway/internal/schema"
)

const (
	DefaultWorkerCount = 4
	DefaultQuorum      = 3
	DefaultTimeout     = 1200 * time.Millisecond
)

type Config struct {
	WorkerCount int
	Quorum      int
	Timeout     time.Duration
}

type Coordinator struct {
	parser     parser.IdeaParser
	limiter    *TokenBucket
	config     Config
	bufferPool sync.Pool
	ideaPool   sync.Pool
}

type WorkerResult struct {
	WorkerID int
	Idea     schema.BusinessIdea
	Err      error
}

func New(p parser.IdeaParser, limiter *TokenBucket, cfg Config) *Coordinator {
	if cfg.WorkerCount <= 0 {
		cfg.WorkerCount = DefaultWorkerCount
	}
	if cfg.Quorum <= 0 || cfg.Quorum > cfg.WorkerCount {
		cfg.Quorum = DefaultQuorum
	}
	if cfg.Timeout <= 0 {
		cfg.Timeout = DefaultTimeout
	}

	return &Coordinator{
		parser:  p,
		limiter: limiter,
		config:  cfg,
		bufferPool: sync.Pool{
			New: func() any {
				buf := make([]byte, 0, 2048)
				return &buf
			},
		},
		ideaPool: sync.Pool{
			New: func() any {
				ideas := make([]schema.BusinessIdea, 0, cfg.WorkerCount)
				return &ideas
			},
		},
	}
}

func (c *Coordinator) Evolve(parent context.Context, req schema.EvolutionRequest) (schema.EvolutionResponse, error) {
	if err := validate(req); err != nil {
		return schema.EvolutionResponse{}, err
	}

	start := time.Now()
	ctx, cancel := context.WithTimeout(parent, c.config.Timeout)
	defer cancel()

	results := make(chan WorkerResult, c.config.WorkerCount)
	for workerID := 0; workerID < c.config.WorkerCount; workerID++ {
		go c.runWorker(ctx, workerID, req, results)
	}

	ideasPtr := c.ideaPool.Get().(*[]schema.BusinessIdea)
	*ideasPtr = (*ideasPtr)[:0]
	defer func() {
		*ideasPtr = (*ideasPtr)[:0]
		c.ideaPool.Put(ideasPtr)
	}()

	var errs []string
	failed := 0
	received := 0
	returnedEarly := false

	for received < c.config.WorkerCount {
		select {
		case result := <-results:
			received++
			if result.Err != nil {
				failed++
				errs = append(errs, fmt.Sprintf("worker %d: %v", result.WorkerID, result.Err))
				continue
			}
			*ideasPtr = append(*ideasPtr, result.Idea)
			if len(*ideasPtr) >= c.config.Quorum {
				returnedEarly = true
				cancel()
				return c.responseCopy(*ideasPtr, failed, returnedEarly, start, errs), nil
			}
		case <-ctx.Done():
			failed += c.config.WorkerCount - received
			if len(*ideasPtr) == 0 {
				return schema.EvolutionResponse{}, fmt.Errorf("no ideas recovered before timeout: %w", ctx.Err())
			}
			errs = append(errs, ctx.Err().Error())
			return c.responseCopy(*ideasPtr, failed, false, start, errs), nil
		}
	}

	if len(*ideasPtr) == 0 {
		return schema.EvolutionResponse{}, errors.New("all workers failed to produce parseable ideas")
	}
	return c.responseCopy(*ideasPtr, failed, returnedEarly, start, errs), nil
}

func (c *Coordinator) runWorker(ctx context.Context, workerID int, req schema.EvolutionRequest, out chan<- WorkerResult) {
	if err := c.limiter.Acquire(ctx); err != nil {
		c.emitResult(ctx, out, WorkerResult{WorkerID: workerID, Err: err})
		return
	}

	raw := c.bufferPool.Get().(*[]byte)
	*raw = (*raw)[:0]
	defer func() {
		clear(*raw)
		*raw = (*raw)[:0]
		c.bufferPool.Put(raw)
	}()

	if err := mockProviderPayload(ctx, workerID, req, raw); err != nil {
		c.emitResult(ctx, out, WorkerResult{WorkerID: workerID, Err: err})
		return
	}

	idea, err := c.parser.ParseIdea(ctx, raw)
	c.emitResult(ctx, out, WorkerResult{WorkerID: workerID, Idea: idea, Err: err})
}

func (c *Coordinator) emitResult(ctx context.Context, out chan<- WorkerResult, result WorkerResult) {
	select {
	case out <- result:
	case <-ctx.Done():
	}
}

func (c *Coordinator) responseCopy(ideas []schema.BusinessIdea, failed int, returnedEarly bool, start time.Time, errs []string) schema.EvolutionResponse {
	copied := make([]schema.BusinessIdea, len(ideas))
	copy(copied, ideas)
	return schema.EvolutionResponse{
		Ideas:             copied,
		SuccessfulWorkers: len(copied),
		FailedWorkers:     failed,
		ReturnedEarly:     returnedEarly,
		ElapsedMS:         time.Since(start).Milliseconds(),
		Errors:            errs,
	}
}

func validate(req schema.EvolutionRequest) error {
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

func mockProviderPayload(ctx context.Context, workerID int, req schema.EvolutionRequest, dst *[]byte) error {
	delay := []time.Duration{
		90 * time.Millisecond,
		140 * time.Millisecond,
		190 * time.Millisecond,
		1500 * time.Millisecond,
	}
	if workerID < len(delay) {
		timer := time.NewTimer(delay[workerID])
		defer timer.Stop()
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-timer.C:
		}
	}

	conceptCost := req.Budget * (0.18 + float64(workerID)*0.07)
	payloads := []string{
		`Here is the strongest concept:
{"concept_name":"Local AI Workflow Studio","estimated_startup_cost":%.2f,"feasibility_score":0.91,"risk_factors":["customer education","API cost variance",],"marketing_angle":"Done-for-you automations for %s operators in %s"`,
		"```json\n{\"concept_name\":\"Micro SaaS Launch Lab\",\"estimated_startup_cost\":%.2f,\"feasibility_score\":0.87,\"risk_factors\":[\"crowded market\",\"support load\"],\"marketing_angle\":\"Launch a narrow %s tool in %s with fixed-scope onboarding\",}\n```",
		`Analysis follows. [{"concept_name":"Neighborhood Ops Copilot","estimated_startup_cost":%.2f,"feasibility_score":0.84,"risk_factors":["data quality","local partnerships"],"marketing_angle":"A pragmatic AI assistant for %s teams around %s"}] extra commentary`,
		`{"concept_name":"Stalled Provider Idea","estimated_startup_cost":%.2f,"feasibility_score":0.72,"risk_factors":["slow upstream"],"marketing_angle":"Recovered only if timeout allows"}`,
	}
	idx := workerID % len(payloads)
	*dst = fmt.Appendf(*dst, payloads[idx], conceptCost, req.TargetSector, req.Location)
	return nil
}
