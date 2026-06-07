package coordinator

import (
	"context"
	"time"
)

type TokenBucket struct {
	tokens chan struct{}
	stop   chan struct{}
}

func NewTokenBucket(capacity int, refillEvery time.Duration) *TokenBucket {
	b := &TokenBucket{
		tokens: make(chan struct{}, capacity),
		stop:   make(chan struct{}),
	}
	for i := 0; i < capacity; i++ {
		b.tokens <- struct{}{}
	}

	go func() {
		ticker := time.NewTicker(refillEvery)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				select {
				case b.tokens <- struct{}{}:
				default:
				}
			case <-b.stop:
				return
			}
		}
	}()
	return b
}

func (b *TokenBucket) Acquire(ctx context.Context) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-b.tokens:
		return nil
	}
}

func (b *TokenBucket) Close() {
	close(b.stop)
}
