# Template Orchestrator

Copy this directory to bootstrap a new department orchestrator service.

## Usage

```bash
cp -r services/_template-orchestrator services/{dept}-orchestrator
```

Then find-and-replace these placeholders:
- `{DEPT_ID}` — lowercase dept slug (e.g. `finance`)
- `{DEPT_NAME}` — human-readable name (e.g. `Finance`)
- `{PORT}` — service port (3010+)
- `{AGENT_NAME}` — agent names for specialists

## Onboarding Checklist

See framework spec S5 for the full 12-step department onboarding process.
