# T07 offline acceptance — 20 September 2026

Status: offline implementation complete; real-model integration remains blocked.
The approved configuration is in [the plan](t07-plan.md) and Architecture D05/D06.
Implementation details and usage are in [retrieval/README.md](../src/binfocheck/retrieval/README.md).
No shared domain/schema change, T04 dependency or T11B StepAttempt orchestration.

## Checks

- Required retrieval suite: 36 synthetic tests passed. Coverage includes separate
  input routing, German numbers/units/negation, hand-calculated RRF, top-50/full
  union, overflow before any encoding, corpus/model/dimension/config guards,
  missing/corrupt artifacts, saved contexts, SQLite reopen/rescore/replay and
  interrupted publication without replacing earlier results.
- Full `scripts/verify.sh`: 974 tests passed after synchronization with main;
  lint, formatting, type checks, schema drift and staged/unstaged whitespace checks
  also passed.
- Saved T06 corpus: five articles / 228 passages; synthetic diagnostic driving claim
  and synthetic vectors. Both paths returned 50 hits; their full union contained
  88 candidates. SQLite close/reopen, index reload, rescoring and exact saved-result
  replay passed with sockets/DNS disabled. This is plumbing validation, not Harrier
  acceptance or a recall measurement. Original T06 data was not modified.
- No real model/provider calls, no model-weight download; actual model/provider
  tokens and cost are zero. Public metadata/source reads and package installation
  were separate. Deployed checks are not applicable.

## Saved-corpus artifacts

Private test store/report: `/tmp/binfocheck-t07-real-corpus-v1/t07-report.json`.
Reproduction script: `/tmp/binfocheck-t07-real-corpus-check.py` (run with
`PYTHONPATH=. .venv/bin/python /tmp/binfocheck-t07-real-corpus-check.py`).
These are temporary test artifacts; the original durable corpus is identified by
[the T06 handoff](t06-handoff.md). Neither real source text nor the store is committed.

## Remaining local-model gate

The exact Harrier revision is `f9b9dc8d367d443f2479d27aa5d8d2850c0774ee`.
`LocalHarrier.open` against the available Hugging Face cache returned
`local_model_unavailable` before importing a model. No substitute was used.

A separately authorized setup step must provision this snapshot and the locked
`local-model` extra. Then run real-tokenizer preflight on all heading-plus-passage
inputs, prepare the 1024-dimensional index and diagnostic query, retrieve, and
verify saved reload/rescore/replay without model/network calls. Overflow must stop
preparation and identify the passage. No model comparison or benchmark is required.
