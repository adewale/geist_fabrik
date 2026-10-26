# Topic selection rationale

The [current design](TOPICS.md) separates hard source boundaries from fallible
relevance rules. The controlled [experiment plan](../benchmarks/corpora/topic_policy_experiment.json)
freezes the comparison, selection order and boilerplate tradeoff before new output.
Every added rule is ablated; unchanged known-answer tests and independent fresh
annotations supply distinct kinds of evidence. No new held-out measurement is
used to tune a later policy.

Earlier document-global grammar improved the model proxies, but could let an
unrelated clause change another candidate's eligibility. The replacement judges
only the mapped sentence, retains uncertainty and exposes stable reasons. Exact
source wording/offsets and conservative topic identities remain unchanged.

An unused caption such as `Three important action items today` can have the same
list/grammar structure as `Three important relation properties today` above
`Reflexive:`, `Symmetric:` and `Transitive:` fields. Blank children alone cannot
justify deleting the parent. The original rare-outline regression protected leaf
subjects; the later parent-caption regression closes that coverage gap. Both
remain unchanged. Filled form responses receive their own protected controls.

The [historical raw probes](../benchmarks/archives/topics/README.md) retain the
measured regressions from removing link priors, cutting the label budget and
changing block scoring. They are calibration history, not proof of the new policy.
No domain word list, corpus frequency floor, excluded-template reading or source
rewrite is introduced to force a pass. The old empty-form failure remains a
quality failure. See [verification](TOPICS_VERIFICATION.md).
