//go:build darwin

package ranking

import (
	"math"
	"testing"
)

func TestRankIdeasEmpty(t *testing.T) {
	if got := RankIdeas(nil); got != 0 {
		t.Fatalf("RankIdeas(nil) = %v, want 0", got)
	}
	if got := RankIdeas([]float32{}); got != 0 {
		t.Fatalf("RankIdeas(empty) = %v, want 0", got)
	}
}

func TestRankIdeasSmallSum(t *testing.T) {
	got := RankIdeas([]float32{1, 2, 3, 4})
	if got != 10 {
		t.Fatalf("RankIdeas = %v, want 10", got)
	}
}

func TestRankIdeasLargeSum(t *testing.T) {
	scores := make([]float32, 10000)
	var want float32
	for i := range scores {
		scores[i] = float32(i%17) * 0.25
		want += scores[i]
	}

	got := RankIdeas(scores)
	if math.Abs(float64(got-want)) > 0.01 {
		t.Fatalf("RankIdeas = %v, want %v", got, want)
	}
}
