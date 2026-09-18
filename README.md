# BinfoCheck

| | | | |
| --- | --- | --- | --- |
| **License** | [![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE) | **Python** | [![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](.python-version) |
| **Build** | [![CI](https://github.com/dyusuf/BinfoCheck/actions/workflows/ci.yml/badge.svg)](https://github.com/dyusuf/BinfoCheck/actions/workflows/ci.yml) | **Status** | MVP in development |

**Auditable measurement of citations and uncited content overlap in AI-generated search results.**

BinfoCheck helps publishers investigate a practical question:

> **When does AI search cite our website, and when do its answers match our content without citing us?**

## Description

BinfoCheck captures AI-search answers, extracts factual claims, records visible citations, and compares uncited claims with a website's published content.

It distinguishes common information from more distinctive overlap and preserves the evidence behind each finding for human review.

A content match does **not** prove that an AI system used a particular website as its source. BinfoCheck measures evidence of overlap, not provenance.

**First pilot:** German Google AI Mode results compared with selected [diabinfo.de](https://www.diabinfo.de/) content. The monitored website remains configurable.

## Workflow

```text
AI-search results
→ claim extraction
→ citation check
→ content matching
→ distinctiveness assessment
→ evidence classification
→ editorial review
```

## Documentation

- [MVP scope](docs/mvp.md)
- [Architecture](docs/architecture.md)
- [Implementation plan](docs/implementation-plan.md)
- [Beyond MVP](docs/beyond-mvp.md)
- [Coding-agent instructions](AGENTS.md)

## Current status

The MVP is under development. The current implementation establishes the shared contracts and infrastructure required by the later measurement pipeline.

## License

See [LICENSE](LICENSE).
