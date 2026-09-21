# BinfoCheck

| | | | |
| --- | --- | --- | --- |
| **License** | [![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE) | **Python** | [![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](.python-version) |
| **Build** | [![CI](https://github.com/dyusuf/BinfoCheck/actions/workflows/ci.yml/badge.svg)](https://github.com/dyusuf/BinfoCheck/actions/workflows/ci.yml) | **Status** | MVP in development |

**When does AI search cite your site, and when do uncited answers contain claims that match your content?**

BinfoCheck measures both. It compares claims in AI-generated search results with a website's published content and gives editors the source evidence behind each finding.

A match does **not** prove that the AI used that website as its source. BinfoCheck distinguishes common overlap from more distinctive matches and preserves the evidence for human review.

The MVP is designed to prove one core loop:

```text
AI observation
→ citation-first check
→ claim extraction
→ corpus retrieval
→ distinctive-overlap evidence
→ editor verification
```

**First pilot:** German Google AI Mode results compared with selected [diabinfo.de](https://www.diabinfo.de/) content.

## Documentation

- [MVP scope](docs/mvp.md)
- [Architecture](docs/architecture.md)
- [Implementation plan](docs/implementation-plan.md)
- [Beyond MVP](docs/beyond-mvp.md)
- [Coding-agent instructions](AGENTS.md)
- [Development workflow and offline verification](docs/development-workflow.md)

## Current status

The MVP is under development. Task states below are a generated public summary of the
official acceptance state maintained in the implementation plan.

<!-- TASK-STATUS:START -->
| Task | Component | Status |
|---|---|---|
| T00 | Contracts, scaffold and CI | ✅ Accepted |
| T11A | Shared storage | ✅ Accepted |
| T01 | Google AI Mode acquisition | ✅ Accepted |
| T02 | Answer indexing/context | ✅ Accepted |
| T03 | Model adapters | 🟡 Integration blocked |
| T04 | Claim extraction | 🟡 Integration blocked |
| T05 | Citation mapping | 🟡 Integration blocked |
| T06 | diabinfo.de corpus | ✅ Accepted |
| T07 | Hybrid retrieval | ✅ Accepted |
| T08 | Candidate verification | ⚪ Not started |
| T09 | Alternative-source analysis | ⚪ Not started |
| T10 | Evidence classification | ⚪ Not started |
| T11B | Pipeline execution | ⚪ Not started |
| T12 | API | ⚪ Not started |
| T13 | Editorial dashboard | ⚪ Not started |
| T14 | End-to-end/deployment | ⚪ Not started |

Detailed acceptance criteria and evidence are maintained in the
[implementation plan](docs/implementation-plan.md).
<!-- TASK-STATUS:END -->
