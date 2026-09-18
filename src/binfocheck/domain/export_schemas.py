"""Generate schemas, or check committed exports without changing them."""

import argparse
import json
from pathlib import Path

from .catalog import schema_catalog

DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "schemas" / "v1"


def render_schemas() -> dict[str, str]:
    return {
        f"{name}.json": json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        for name, schema in schema_catalog().items()
    }


def check_schemas(directory: Path) -> list[str]:
    expected = render_schemas()
    actual = {path.name for path in directory.glob("*.json")}
    differences = [f"unexpected: {name}" for name in sorted(actual - expected.keys())]
    for name, content in expected.items():
        path = directory / name
        if not path.exists():
            differences.append(f"missing: {name}")
        elif path.read_text(encoding="utf-8") != content:
            differences.append(f"changed: {name}")
    return differences


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output: Path = args.output
    if args.check:
        differences = check_schemas(output)
        for difference in differences:
            print(difference)
        if differences:
            return 1
        print("Contract schemas match the Python types.")
        return 0
    output.mkdir(parents=True, exist_ok=True)
    for name, content in render_schemas().items():
        (output / name).write_text(content, encoding="utf-8")
    print(f"Exported {len(render_schemas())} schemas to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
