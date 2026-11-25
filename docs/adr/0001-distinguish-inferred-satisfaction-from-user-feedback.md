# Distinguish inferred satisfaction from observed user feedback

Status: Implemented and reviewed as opt-in rule version 3; independent validation pending.

ConvoSignal will allow supported completion of the user's goal to justify an
inferred satisfaction judgment even when the user's reaction is unknown. This
expands coverage beyond requiring acknowledgment of every material requirement,
while keeping task completion, explicit feedback and correctness distinct: silence
alone does not establish success, reading or session closure. Unsupported figures
without acceptance or corroboration remain Neutral, and a verified correction
after explicit rejection remains Neutral until acceptance/use confirms recovery.
The user approved all 18 boundaries across six rounds of the
[criteria interview](../../convosignal/docs/criteria-revision-plan.md); current
version 2 code and historical pilot results are unchanged. The user's subsequent
to-spec request published the
[implementation specification](../../.scratch/convosignal-criteria-revision/spec.md).
