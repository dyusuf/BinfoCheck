# BinfoCheck — MVP

**Version:** 1.1 · 18 September 2026  
**Status:** Scope agreed; implementation and measurement validation pending.

## 1. Goal

Detect potential **“invisible use” of diabinfo.de health information in AI-search
answers**, with evidence an editor can inspect.

The question is: **Does an answer contain information matching diabinfo without
crediting it?** We measure citations, overlap and apparent distinctiveness—not
proof that the AI used diabinfo. Initial automated findings are provisional.

## 2. Primary user

The diabinfo editorial team can inspect findings and evidence, then confirm,
reject or correct results without developer assistance. The MVP is German-first.

## 3. Evidence categories

| Category | Meaning |
|---|---|
| **1. Cited diabinfo match** | A visible diabinfo citation is associated with the claim. Despite the retained label, this establishes citation presence only—not source support. |
| **2. Uncited generic match** | The claim matches diabinfo, and inspected alternative material contains the same information. |
| **3. Uncited distinctive match** | More specific or unusual details match, but plausible alternative sources remain. |
| **4. Uncited highly distinctive match** | Unusually close details, wording or examples match, with limited competing explanation in the inspected material. |

**Even Category 4 does not prove provenance.** Missing alternatives alone cannot
justify it. A claim may instead have **No match found in the selected corpus**,
**Citation unclear**, or **Not enough evidence**. Processing failures are separate.

## 4. Core workflow

```text
Collect AI answers → extract claims → check citations
                                         ├─ Diabinfo cited → Category 1
                                         ├─ Unclear → keep unresolved
                                         └─ Not cited → match against diabinfo
                                                        → assess distinctiveness
                                                        → record finding
All findings → editor inspection and review
```

Citation handling is per claim. One answer can contain both cited claims and
uncited matches. Cited claims skip overlap analysis; unclear claims are not counted
as definitely uncited. Answer-level citation statistics are separate.

## 5. Main measurements

| Measurement | Definition |
|---|---|
| **Answer-level citation rate** | Answers with a visible diabinfo citation divided by successfully captured answers whose citation data can be assessed. |
| **Claim findings** | Counts by category, no-match and unresolved status; count a claim once, not once per passage. |
| **Review status** | Awaiting review, confirmed, rejected or corrected; keep automated and reviewed results separate. |

Show every rate's numerator, denominator and exclusions. Expose capture failures
and missing data instead of counting them as negatives.

Tie results to the question set, product, language, collection settings and corpus
version. Keep deliberately selected diagnostic cases separate from monitoring
summaries; neither represents all AI-search activity. Editor confirmation means
agreement with a finding, not proof of hidden use. Review agreement measures the
detector, not the prevalence of invisible use.

## 6. Included scope

### Pilot

Use **Google AI Mode**, German, a fixed Germany location and a supported device
configuration. Select a small fixed set of short German questions; exact wording
and count remain open. Each capture starts a fresh query, not a continuing chat.

Capture these five German HTML articles:

| Page | Testing purpose, not a predetermined category |
|---|---|
| [Driving](https://www.diabinfo.de/leben/diabetes-im-alltag/strassenverkehr.html) | Shared guidance and claim-level citations |
| [Ramadan](https://www.diabinfo.de/leben/diabetes-im-alltag/ramadan.html) | Detailed advice and existing citation examples |
| [Travel](https://www.diabinfo.de/leben/diabetes-im-alltag/reisen.html) | Specific-looking numbers that may be shared |
| [Risk-test FAQ](https://www.diabinfo.de/vorbeugen/diabetes/wie-hoch-ist-mein-risiko-fuer-diabetes-typ-2/haeufig-gestellte-fragen.html) | Potentially distinctive explanations |
| [Motivation tips](https://www.diabinfo.de/vorbeugen/was-kann-ich-tun/so-erreichen-sie-ihre-ziele.html) | Specific examples versus generic advice |

Save full article text and structure, not only expected matches. Record snapshot
dates during ingestion. Do not select pages or questions to force a category.

### Product

Include capture, versioned source content, traceable claims, citation mapping,
matching, provisional classification and saved reviews through a deployed API and
dashboard. Use captured alternative-source excerpts only; no extra page fetching
or independent web search in the initial implementation.

Require basic correctness tests, CI, containers, health checks and operational
monitoring. Preserve originals and processing records for inspection and replay.

## 7. Outside this MVP

No citation fidelity, medical fact-checking, meaning-change analysis, systematic
benchmarking/calibration, additional languages/products, independent web search,
CMS plugin, automated rewriting or large-scale monitoring.

[Architecture](architecture.md) defines implementation.
[Beyond MVP](beyond-mvp.md) lists deferred work.

## 8. Completion criteria

An editor can open a captured answer, inspect claims, citations, matching passages
and available alternatives, understand the provisional finding or unresolved
status, and save a review. The API exposes the same records.

A bounded run shows progress and failures. Original observations, source versions
and past decisions survive reprocessing. Offline, live and deployed checks must
pass as defined in the implementation plan.

**A Category 4 example is not required.** Shared information and insufficient
evidence are valid findings.
