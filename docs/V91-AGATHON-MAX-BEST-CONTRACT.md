# V91 Agathon — MAX-BEST Improvement Contract

Status: DOCUMENTED. This contract defines intended behavior; it does not claim that the behavior is implemented, running, or verified.

## Purpose

Every component contributes the best result it can reasonably achieve with its actual capabilities, evidence, permissions, time, and resource budget. Improve where there is a justified benefit; preserve what works; never confuse effort, confidence, or a status label with proof.

The shared core protocol is documented in `docs/V91-MAX-BEST-PROTOCOL.md` in the `v91-core-system` repository.

## Required cycle

1. **Observe:** Read available evidence. Missing, stale, or invalid measurements are `UNKNOWN`, not zero and not success.
2. **Baseline:** Record the current revision, inputs, relevant measurements, test results, and known gaps.
3. **Choose:** Prioritize safety, recovery, human dignity, ecological integrity, and reliability before optimization for its own sake.
4. **Plan:** State the expected benefit, acceptance criteria, possible side effects, required authorization, resource budget, and safe rollback path.
5. **Isolate:** Test candidate changes away from protected/default state. Treat external or model-generated content as untrusted data until validated.
6. **Validate:** Run reproducible checks against the baseline. Record the exact revision, environment, commands, results, and artifacts.
7. **Compare:** Accept a change only when evidence supports the expected benefit and required safety/reliability checks show no detected regression.
8. **Promote:** Keep changes separate from the default or production state until review and explicit authorization.
9. **Recover:** On failed checks, broken evidence chains, or detected regressions, block promotion; restore a known-good state only when safe and authorized.
10. **Learn:** Preserve both successful findings and failed hypotheses with provenance. Start the next cycle from evidence, not assumed success.

## Agathon-specific safeguards

- Missing or invalid ecological measurements must remain explicitly unknown.
- Do not infer environmental improvement from a score alone; identify the measurement, time window, source, and limitations.
- A damaged or inconsistent audit chain must not be silently accepted.
- Do not claim that ecological harm was prevented unless the evidence supports that conclusion.
- Avoid unnecessary resource use and complexity; optimization must have a defensible benefit.
- Detection is not authorization. No self-granted privileges, destructive action, or external enforcement.
- If evidence or authorization is insufficient, fail closed for the affected operation and report the limitation.

## Evidence labels

- `UNKNOWN`: evidence is insufficient or unavailable.
- `DOCUMENTED`: this contract or requirement is written down.
- `IMPLEMENTED`: code exists at a named revision.
- `VERIFIED`: a specific reproducible check passed for a specific revision and environment.
- `PRODUCTION`: actual deployment and operational acceptance are evidenced.

Documentation alone establishes only `DOCUMENTED`. A hash can support integrity checking but does not by itself prove correctness, safe operation, or real-world impact.

## Report every cycle

Record the goal, baseline, evidence sources, missing data, proposed change, risks, authorization, tests, regression comparison, final status, artifact/revision references, rollback outcome, and next highest-value safe improvement.

## Acceptance rule

**Do the best reasonably possible. Improve what evidence shows can be improved. Preserve what works. Report uncertainty honestly. Do not claim more than the evidence proves.**

This document does not itself implement these controls or establish that Agathon is operating autonomously.
