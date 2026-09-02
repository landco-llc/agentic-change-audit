# ACA local model-selection addendum

This public-safe addendum records ACA's local reference to the accepted
central routing semantics for bounded work. It does not activate, replace, or
make a claim about the lifecycle status of any central policy source.

| Profile | Model / reasoning | Sandbox | ACA use |
| --- | --- | --- | --- |
| `reconciliation` | `gpt-5.6-luna` / `low` | `workspace-write` | deterministic evidence reconciliation |
| `implementation_mechanical` | `gpt-5.6-luna` / `medium` | `workspace-write` | exact mechanical changes |
| `implementation_standard` | `gpt-5.6-luna` / `medium` | `workspace-write` | bounded standard implementation |
| `implementation_backend` | `gpt-5.6-terra` / `medium` | `workspace-write` | backend or integration implementation |
| `architecture` | `gpt-5.6-terra` / `high` | `read-only` | architecture and boundary analysis |
| `audit_standard` | `gpt-5.6-terra` / `medium` | `read-only` | independent fixed-head audit |
| `implementation_critical` | `gpt-5.6-sol` / `high` | `workspace-write` | critical implementation |
| `audit_critical` | `gpt-5.6-sol` / `high` | `read-only` | critical independent audit |

The Parent selects the smallest profile consistent with the work record,
scope, risk, and escalation criteria. A profile must not widen scope or merge,
release, deployment, provider, or Human Gate authority. Audit and correction
remain separate contexts; a changed head requires a fresh independent re-audit.
