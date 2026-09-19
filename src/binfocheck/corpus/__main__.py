"""Offline replay/inspection only. This CLI cannot initiate a live capture."""

import argparse
import json
from pathlib import Path

from binfocheck.domain.interfaces import IngestionRequest
from binfocheck.storage import SQLiteStore

from .config import PACKAGES, POLICY, URLS
from .ingestion import StoredCorpusIngestor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("proposed-policy", help="print frozen proposal; does not authorize capture")
    for name in ("replay", "inspect"):
        command = commands.add_parser(name)
        command.add_argument("--store", type=Path, required=True)
        command.add_argument("--request" if name == "replay" else "--manifest", required=True)
    args = parser.parse_args(argv)
    if args.command == "proposed-policy":
        print(
            json.dumps(
                {
                    "authorized": False,
                    "urls": URLS,
                    "packages": PACKAGES,
                    "policy": POLICY.model_dump(mode="json"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    with SQLiteStore(args.store) as store:
        ingestor = StoredCorpusIngestor(store, store)
        if args.command == "replay":
            request = IngestionRequest.model_validate_json(Path(args.request).read_bytes())
            outcome = ingestor.ingest(request)
        else:
            outcome = ingestor.load(args.manifest)
        if outcome.value is None:
            print(
                json.dumps(
                    {"status": "failed", "error": outcome.error.code if outcome.error else None}
                )
            )
            return 1
        result = outcome.value
        print(
            json.dumps(
                {
                    "manifest_id": result.manifest.id,
                    "status": result.manifest.status,
                    "articles": [
                        {
                            "id": a.id,
                            "url": a.url,
                            "status": a.status,
                            "reason": a.reason,
                            "sha256": a.content_sha256,
                            "passages": sum(p.article_version_id == a.id for p in result.passages),
                        }
                        for a in result.articles
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if result.manifest.status == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
