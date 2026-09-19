# BinfoCheck

| | | | |
| --- | --- | --- | --- |
| **License** | [![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE) | **Python** | [![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](.python-version) |
| **Build** | [![CI](https://github.com/dyusuf/BinfoCheck/actions/workflows/ci.yml/badge.svg)](https://github.com/dyusuf/BinfoCheck/actions/workflows/ci.yml) | **Status** | MVP in development |

**When does AI search cite your site, and when do uncited answers contain claims that match your content?**

BinfoCheck measures both. It compares claims in AI-generated search results with a website's published content and gives editors the source evidence behind each finding.

A match does **not** prove that the AI used that website as its source. BinfoCheck distinguishes common overlap from more distinctive matches and preserves the evidence for human review.

**First pilot:** German Google AI Mode results compared with selected [diabinfo.de](https://www.diabinfo.de/) content.

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
