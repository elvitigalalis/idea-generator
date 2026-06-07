package schema

type BusinessIdea struct {
	ConceptName          string   `json:"concept_name"`
	EstimatedStartupCost float64  `json:"estimated_startup_cost"`
	FeasibilityScore     float64  `json:"feasibility_score"`
	RiskFactors          []string `json:"risk_factors"`
	MarketingAngle       string   `json:"marketing_angle"`
}

type EvolutionRequest struct {
	Budget       float64 `json:"budget"`
	Location     string  `json:"location"`
	TargetSector string  `json:"target_sector"`
	Generations  int     `json:"generations"`
	SeedCount    int     `json:"seed_count"`
}

type EvolutionResponse struct {
	Ideas                   []BusinessIdea `json:"ideas"`
	SuccessfulWorkers       int            `json:"successful_workers"`
	FailedWorkers           int            `json:"failed_workers"`
	ReturnedEarly           bool           `json:"returned_early"`
	ElapsedMS               int64          `json:"elapsed_ms"`
	AggregateScore          float32        `json:"aggregate_score"`
	AverageFeasibilityScore float32        `json:"average_feasibility_score"`
	Errors                  []string       `json:"errors,omitempty"`
}
