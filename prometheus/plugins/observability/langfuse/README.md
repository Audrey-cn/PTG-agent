# Langfuse Observability Plugin

This plugin ships bundled with Prometheus but is **opt-in** — it only loads when
you explicitly enable it.

## Enable

Pick one:

```bash
# Interactive: walks you through credentials + SDK install + enable
prometheus tools  # → Langfuse Observability

# Manual
pip install langfuse
prometheus plugins enable observability/langfuse
```

## Required credentials

Set these in `~/.prometheus/.env` (or via `prometheus tools`):

```bash
prometheus_LANGFUSE_PUBLIC_KEY=pk-lf-...
prometheus_LANGFUSE_SECRET_KEY=sk-lf-...
prometheus_LANGFUSE_BASE_URL=https://cloud.langfuse.com   # or your self-hosted URL
```

Without the SDK or credentials the hooks no-op silently — the plugin fails
open.

## Verify

```bash
prometheus plugins list                 # observability/langfuse should show "enabled"
prometheus chat -q "hello"              # then check Langfuse for a "Prometheus turn" trace
```

## Optional tuning

```bash
prometheus_LANGFUSE_ENV=production       # environment tag
prometheus_LANGFUSE_RELEASE=v1.0.0       # release tag
prometheus_LANGFUSE_SAMPLE_RATE=0.5      # sample 50% of traces
prometheus_LANGFUSE_MAX_CHARS=12000      # max chars per field (default: 12000)
prometheus_LANGFUSE_DEBUG=true           # verbose plugin logging
```

## Disable

```bash
prometheus plugins disable observability/langfuse
```
