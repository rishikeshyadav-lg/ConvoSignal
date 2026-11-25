# ConvoSignal implementation

Status: ready-for-agent
Date: 2026-11-24

The user authorized implementation and dependency additions for this session.
Functional C0–C3/C5 and comparison tooling are complete. C4 independent human
validation remains pending. ConvoSignal milestones remain separate from
Account360's current M0.

- [Behavior and acceptance](../../convosignal/docs/Prod-Spec.md)
- [Architecture and CLI](../../convosignal/docs/Architecture.md)
- [Milestones](../../convosignal/docs/Milestones.md)
- [Original complete brief](../../convosignal/docs/original-brief.md)

## Issues

| Issue | Blocked by |
| --- | --- |
| [01 Contracts and rules](issues/01-contracts-and-rules.md) | Complete; available for review |
| [02 Extraction and filtering](issues/02-extraction-and-filtering.md) | Complete; available for review |
| [03 Offline workflow](issues/03-offline-workflow.md) | 01, 02 |
| [04 Live integrations](issues/04-live-integrations.md) | 03; model endpoint configuration |
| [05 Independent evaluation](issues/05-independent-evaluation.md) | 04; independent reviewer labels |
| [06 Delivery checks](issues/06-delivery-checks.md) | 03, 04; report 05 validation state separately |
| [07 Criteria revision](issues/07-criteria-revision.md) | Ready-for-agent specification published |

Criteria revision: [published specification](../convosignal-criteria-revision/spec.md)
— ready-for-agent, with implementation separate from independent validation.

## Comments

- 2026-11-24: User selected convosignal/ and requested a plan for revised criteria.
  Concrete apparent recovery without user feedback becomes Neutral /
  recovery_unconfirmed; the original brief is preserved.
