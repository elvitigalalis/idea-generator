package parser

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"

	"idea-evolution-engine/services/gateway/internal/schema"
)

var (
	ErrNoJSONFound   = errors.New("no json object or array found")
	ErrRustFFINotSet = errors.New("rust ffi parser is not configured")
)

type IdeaParser interface {
	ParseIdea(ctx context.Context, raw *[]byte) (schema.BusinessIdea, error)
	ParseIdeas(ctx context.Context, raw *[]byte, dst *[]schema.BusinessIdea) ([]schema.BusinessIdea, error)
}

type PureGoRepairParser struct{}

func NewPureGoRepairParser() *PureGoRepairParser {
	return &PureGoRepairParser{}
}

// RustFFIParser is the Phase 2 insertion point. It intentionally satisfies the
// same constructor-level dependency shape as the pure Go parser, so coordinator
// and HTTP packages remain untouched when native repair is wired in.
type RustFFIParser struct{}

func NewRustFFIParser() *RustFFIParser {
	return &RustFFIParser{}
}

func (p *RustFFIParser) ParseIdea(context.Context, *[]byte) (schema.BusinessIdea, error) {
	return schema.BusinessIdea{}, ErrRustFFINotSet
}

func (p *RustFFIParser) ParseIdeas(context.Context, *[]byte, *[]schema.BusinessIdea) ([]schema.BusinessIdea, error) {
	return nil, ErrRustFFINotSet
}

func (p *PureGoRepairParser) ParseIdea(ctx context.Context, raw *[]byte) (schema.BusinessIdea, error) {
	var ideas []schema.BusinessIdea
	parsed, err := p.ParseIdeas(ctx, raw, &ideas)
	if err != nil {
		return schema.BusinessIdea{}, err
	}
	if len(parsed) == 0 {
		return schema.BusinessIdea{}, errors.New("json decoded but contained no ideas")
	}
	return parsed[0], nil
}

func (p *PureGoRepairParser) ParseIdeas(ctx context.Context, raw *[]byte, dst *[]schema.BusinessIdea) ([]schema.BusinessIdea, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if raw == nil {
		return nil, errors.New("nil raw payload")
	}

	candidate, err := extractJSONCandidate(*raw)
	if err != nil {
		return nil, err
	}

	if ideas, err := decodeCandidate(candidate, dst); err == nil {
		return ideas, nil
	}

	candidate = removeTrailingCommasInPlace(candidate)
	if ideas, err := decodeCandidate(candidate, dst); err == nil {
		return ideas, nil
	}

	repaired := balanceJSON(candidate)
	repaired = removeTrailingCommasInPlace(repaired)
	if ideas, err := decodeCandidate(repaired, dst); err == nil {
		return ideas, nil
	} else {
		return nil, fmt.Errorf("unable to repair json payload: %w", err)
	}
}

func extractJSONCandidate(raw []byte) ([]byte, error) {
	raw = stripMarkdownFence(raw)
	start := bytes.IndexAny(raw, "{[")
	if start < 0 {
		return nil, ErrNoJSONFound
	}

	open := raw[start]
	close := byte('}')
	if open == '[' {
		close = ']'
	}

	depth := 0
	inString := false
	escaped := false
	lastClose := -1

	for i := start; i < len(raw); i++ {
		b := raw[i]
		if inString {
			if escaped {
				escaped = false
				continue
			}
			if b == '\\' {
				escaped = true
				continue
			}
			if b == '"' {
				inString = false
			}
			continue
		}

		switch b {
		case '"':
			inString = true
		case open:
			depth++
		case close:
			depth--
			lastClose = i
			if depth == 0 {
				return raw[start : i+1], nil
			}
		}
	}

	if lastClose >= start {
		return raw[start : lastClose+1], nil
	}
	return raw[start:], nil
}

func stripMarkdownFence(raw []byte) []byte {
	trimmed := bytes.TrimSpace(raw)
	if !bytes.HasPrefix(trimmed, []byte("```")) {
		return trimmed
	}

	firstNewline := bytes.IndexByte(trimmed, '\n')
	if firstNewline < 0 {
		return trimmed
	}
	body := trimmed[firstNewline+1:]
	if end := bytes.LastIndex(body, []byte("```")); end >= 0 {
		body = body[:end]
	}
	return bytes.TrimSpace(body)
}

func removeTrailingCommasInPlace(buf []byte) []byte {
	write := 0
	for read := 0; read < len(buf); read++ {
		if buf[read] == ',' {
			next := read + 1
			for next < len(buf) && isJSONSpace(buf[next]) {
				next++
			}
			if next < len(buf) && (buf[next] == '}' || buf[next] == ']') {
				continue
			}
		}
		buf[write] = buf[read]
		write++
	}
	clear(buf[write:])
	return buf[:write]
}

func balanceJSON(candidate []byte) []byte {
	repaired := make([]byte, 0, len(candidate)+8)
	repaired = append(repaired, candidate...)

	var stack []byte
	inString := false
	escaped := false

	for _, b := range candidate {
		if inString {
			if escaped {
				escaped = false
				continue
			}
			if b == '\\' {
				escaped = true
				continue
			}
			if b == '"' {
				inString = false
			}
			continue
		}
		switch b {
		case '"':
			inString = true
		case '{':
			stack = append(stack, '}')
		case '[':
			stack = append(stack, ']')
		case '}', ']':
			if len(stack) > 0 {
				stack = stack[:len(stack)-1]
			}
		}
	}

	if inString {
		repaired = append(repaired, '"')
	}
	for i := len(stack) - 1; i >= 0; i-- {
		repaired = append(repaired, stack[i])
	}
	return repaired
}

func decodeCandidate(candidate []byte, dst *[]schema.BusinessIdea) ([]schema.BusinessIdea, error) {
	if dst == nil {
		return nil, errors.New("nil destination slice")
	}
	*dst = (*dst)[:0]

	var idea schema.BusinessIdea
	if err := json.Unmarshal(candidate, &idea); err == nil && idea.ConceptName != "" {
		*dst = append(*dst, idea)
		return *dst, nil
	}

	if err := json.Unmarshal(candidate, dst); err != nil {
		return nil, err
	}
	return *dst, nil
}

func isJSONSpace(b byte) bool {
	return b == ' ' || b == '\n' || b == '\r' || b == '\t'
}
