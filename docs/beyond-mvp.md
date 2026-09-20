# BinfoCheck — Beyond MVP

**Version:** 1.2 · 20 September 2026  
**Status:** Backlog, not a schedule or part of [MVP completion](mvp.md#8-completion-criteria).

The MVP supplies observations and editor decisions for later evaluation. Those
records are not automatically a validated benchmark or a representative sample.

## 1. First priority: measurement quality

| Layer | Later work |
|---|---|
| Acquisition | Measure capture completeness, failures, metadata coverage and variation across repeated runs. Do not expect identical results to a personal browser session. |
| Extraction | Compare Claimify-inspired, FActScore-style and other methods on German answers: missed/distorted claims, unresolved references and source-location errors. |
| Citation mapping | Compare against manual mappings; separate mapping uncertainty from citation fidelity. |
| Retrieval | Compare embeddings, lexical settings, passage boundaries and rank fusion. Tune top-k using both found and missed relevant passages. |
| Candidate verification | Test whether this extra stage helps or discards useful passages; compare with direct correspondence judging. |
| Correspondence/classification | Compare Jev and other judges on match labels, evidence categories and unresolved decisions. |
| Alternatives | Test what captured excerpts establish; add targeted web search if needed. |
| Probabilities | Calibrate thresholds; check confident errors, review workload and performance on unseen topics. |

### T07 retrieval follow-ups

- **Embedding-model evaluation:** build a manually reviewed German health retrieval
  benchmark and compare the MVP Harrier model with strong multilingual alternatives.
  Include paraphrases, negation, numbers/units, qualifiers and contradictory evidence.
- **Sub-passage chunking:** if future corpora contain passages that exceed the embedding
  model's supported input length, evaluate deterministic sub-passage chunking while
  keeping the original passage as the authoritative evidence unit.
- **Retrieval-depth tuning:** compare candidate depths such as 20, 50 and 100 for the
  semantic and lexical paths. Measure relevant-passage recall against Jev calls,
  latency and cost rather than tuning top-k during the MVP.

Keep development and held-out examples separate. Review some unflagged cases to
find missed matches. Prevent repeated wording and copies of an article from leaking
across evaluation splits.

Revisit category definitions using real cases; allow categories to remain difficult
to assess or prove unnecessary. Human agreement on overlap is not ground truth for
hidden provenance. Keep detector performance separate from product measurements:
the fraction of flags accepted by editors is not an invisible-use rate.

## 2. Additional analysis

**Citation fidelity:** does the cited page support the claim?

**Meaning changes:** have certainty, population, conditions, numbers, causality or
timeframe changed?

**Provenance research:** test additional acquisition or experimental signals without
treating similarity or reported retrieval as proof of causal use.

These additions must not silently change the meaning of existing MVP categories.

## 3. Product expansion

After reviewing measurement quality, consider more AI-search products, languages,
corpora, scheduled longitudinal monitoring, alerts and reporting.

Add CMS integration and editorial recommendations through the existing API.
A CMS client does not imply automatic rewriting or publication. Increase scale,
deployment complexity or vendor choices only when usage and measured limitations
justify them.

## 4. Boundary with the MVP

Basic tests, source traceability, visible failures and human review remain required
now. Systematic comparisons and calibration are deferred, not unnecessary.
See [Architecture](architecture.md) for the initial implementations.
