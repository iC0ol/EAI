# Research state — spatial understanding for robot action

Last updated: 2026-11-05 (Asia/Shanghai). Search cutoff fixed at 2026-11-05.

## Status: COMPLETE (deliverables written; awaiting researcher review)

## What was done
- Read `/home/asus/EAI/AGENTS.md`, task `AGENTS.md`, `DELEGATION.md`, full `USER_PROMPT.md`.
- Six query rounds (130 boolean queries, ~2,360 unique metadata records) via the public arXiv Atom API.
- 88 papers registered in `sources/papers.jsonl`; 80 full texts obtained (16 PDF + 64 arXiv HTML);
  33 read fully, 12 partially, 43 abstract-only (rate limits).
- 9 original full-text note files in `notes/full_text/`.
- Nearest-neighbour review, search log, final report (7 parts), executive summary, self-audit.

## Headline findings
1. Categories A (cross-view), B (3D representation), C (memory benchmarks), D (active perception systems),
   E (spatial benchmarks) are all crowded by 2026; each has multiple direct competitors with action-level results.
2. The only surviving small-paper opening is **C1: whether action tolerance predicts the action benefit of
   a spatial representation upgrade**. This is a measurement/prediction contribution, not a module.
3. A self-check contradiction is central: KYC's own table shows the largest gain on the *loosest*-tolerance task
   (Lift +27.0 pp) and a small gain on a tight one (AssemblySquare +7.9 pp), so a single-factor tolerance
   hypothesis is false. C1 was reformulated as a three-factor hypothesis (tolerance τ, shortcut reliance s,
   effective error reduction Δε).
4. KYC releases code + data + reproduce configs but **no checkpoints** (MIT). This is the structural reason the
   user's self-trained KYC-ACT baseline was unreliable; 0/32 cannot be explained by task difficulty
   (ACT reference success 10.8–33.6%).

## Key unknowns
- No citation chasing (Semantic Scholar / OpenAlex returned HTTP 429). "Not found" ≠ "does not exist".
- C1's core premise — constructing same-difficulty / different-tolerance task pairs — is unverified.
- 43 papers abstract-only; they could change crowding judgements but not the core claims.

## Next (for the researcher, not this task)
- Read LIBERO-RIG, More Structure, 2610.01626 in full and chase their citations.
- Verify baseline reliability on two tasks before any experiment authorization.
- Decide whether a measurement/prediction paper is acceptable as the small paper.
