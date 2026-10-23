# M-Gate0-L: online replay proxy screen

Independent experiment from `89d89fbcd6458e50ae875746dd1adcdb032ec121`.
Read [the preregistration](reports/protocol.md). All new artifacts stay here.
The subject is a **replayed-prefix surrogate / log-action proxy**, not a recovered
expert demonstration state or a validated expert-supervision label.

No training, reset/solver/cache repair, source-threshold relaxation, second task,
seed43, extra radius, new modules to rescue M, or automatic Gate1. At most160
attempted complete suffix allocations (A4+B1:56+B2:48+B3:52); wall deadline12h.
Large traces stay in ignored `local/` with public SHA indices.

Completed A4 + B1:56 + B2:48 = **108** full suffixes in24.014 minutes.
L-A passed. Only S04 (demo_56,t55), −x failed; all95 other perturbations and
all8 B nominal suffixes succeeded. Directional information came from1/4 dev
episodes, so the preregistered B2 gate stopped. B3:52 allocations remain unrun.

**Practical No-Go for continuing this M version as a quick master's paper.**
No cross-source directional evidence, no validated residual beyond fixed full
3×3/object/contact baselines, and no established true-expert supervision labels.
The isolated ±x asymmetry is a weak warning, below the strong PSD rejection rule.
No new training or Gate1 followed.

- [Five questions and paper decision](reports/paper_viability.md)
- [Signed outcomes and scientific gate](reports/direction_outcome_gate.md)
- [Technical qualification](reports/technical_go_nogo.md)
- [Commands and costs](reports/commands_and_costs.md)
- [Raw data schema](reports/data_dictionary.md)
- [Full160 allocation ledger](outputs/all160_allocations_actual.csv)
- [All12 source states](outputs/all12_states_actual.csv)
- [Raw trajectory index](outputs/trace_index.csv) — public compressed CSV has
  every numeric array; local NPZ is retained and independently roundtrip-checked.
- [Final audit](outputs/final_audit.json)

The old Gate0/R records and conclusions remain unchanged. No further experiments
are authorized by this delivery; await the researcher's review.
