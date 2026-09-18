# BinfoCheck

**Auditable measurement of citations and uncited content overlap in AI-generated search results.**

BinfoCheck is being developed to help publishers answer a practical question:

> **When does AI search cite our website, and when do its answers match our content without citing us?**

The system captures AI-search answers, extracts factual claims, records visible citations, and compares uncited claims with a monitored website's published content. It then distinguishes common/shared information from more distinctive overlap while preserving the evidence behind every finding.

A content match does **not** prove that an AI system used that website as its source. BinfoCheck reports evidence of overlap, not certainty about provenance, and it does not provide medical advice.

**First pilot:** German-language Google AI Mode answers compared with a selected collection of [diabinfo.de](https://www.diabinfo.de/) pages. The design keeps the monitored website configurable; broad multi-site support is outside the first MVP.

## How it works

```text
AI-search observation
        ↓
claim extraction
        ↓
citation check
        ↓
website retrieval + matching
        ↓
distinctiveness assessment
        ↓
evidence classification
        ↓
editorial review
```

BinfoCheck currently uses four evidence levels:

| Level | Meaning |
| --- | --- |
| **Cited website match** | The relevant AI content visibly cites the monitored website. |
| **Uncited generic match** | The claim matches the website, but the information is common elsewhere. |
| **Uncited distinctive match** | The match is more specific or unusual, but plausible alternative sources remain. |
| **Uncited highly distinctive match** | The match contains an unusual combination of details with few visible alternative explanations. |

The system can also return **no match**, **citation unclear**, or **not enough evidence**.

## Current status

The MVP is in development. The current engineering milestone, **T00**, establishes shared data contracts, synthetic fixtures, validation, and repository tooling for the later pipeline components.

## Development

The project uses Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked --dev
```

Run the offline checks:

```bash
uv run --offline --locked pytest
uv run --offline --locked ruff check .
uv run --offline --locked ruff format --check .
uv run --offline --locked pyright
uv run --offline --locked python -m binfocheck.domain.export_schemas --check
git diff --check
```

Tests run without provider credentials or paid API calls. CI runs the same quality checks for pushes to `main` and pull requests targeting `main`.

## Documentation

| Document | Purpose |
| --- | --- |
| [`docs/mvp.md`](docs/mvp.md) | Product scope and MVP completion criteria |
| [`docs/architecture.md`](docs/architecture.md) | Components, contracts, and technical design |
| [`docs/implementation-plan.md`](docs/implementation-plan.md) | Bounded engineering tasks |
| [`docs/beyond-mvp.md`](docs/beyond-mvp.md) | Deferred benchmarking and product extensions |
| [`AGENTS.md`](AGENTS.md) | Repository instructions for coding agents |

## Current implementation

Shared domain models live in `src/binfocheck/domain/`. Versioned JSON Schemas are generated into `schemas/v1/`, and synthetic contract fixtures live under `tests/fixtures/contracts/v1/`.

Detailed record semantics, provenance rules, and component boundaries are documented in [`docs/architecture.md`](docs/architecture.md).

## License

See [`LICENSE`](LICENSE).
