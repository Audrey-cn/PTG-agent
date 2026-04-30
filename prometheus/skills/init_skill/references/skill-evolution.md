---
name: evolution
description: Evolution engine for self-improvement
version: 1.0.0
metadata:
  hermes:
    tags:
      - evolution
      - self-improvement
---

# Evolution Engine

This skill handles the self-evolution protocol: observing patterns, learning from corrections, consulting memory, and verifying rules.

## Protocol

1. **Observe** - Record patterns to observations.jsonl
2. **Learn** - Record user corrections to corrections.jsonl
3. **Consult** - Read learned-rules.md at session start
4. **Verify** - Run verification sweep

## Observation Schema

```json
{
  "timestamp": "ISO-8601",
  "type": "pattern|correction|verification",
  "content": "...",
  "context": "...",
  "confidence": 0.0-1.0
}
```

## Correction Schema

```json
{
  "timestamp": "ISO-8601",
  "original": "...",
  "corrected": "...",
  "feedback": "...",
  "context": "..."
}
```

## Learned Rules

Learned rules are stored in learned-rules.md and should be consulted at the start of each session.
