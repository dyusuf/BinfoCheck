"""Opt-in single capture. Never run by pytest/CI; explicit approval file is required."""

import argparse
import json
from pathlib import Path

from binfocheck.domain.observations import CaptureRequest
from binfocheck.storage import SQLiteStore, StorageInitializationError

from .config import CapturePolicy, Credentials, LiveAuthorization
from .dataforseo import DataForSEOObservationProvider
from .errors import AcquisitionError, PersistenceError, require
from .persistence import load_receipt
from .replay import replay_capture
from .transport import HttpsTransport


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One explicitly authorized DataForSEO capture; no retries"
    )
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    args = parser.parse_args()
    try:
        request = CaptureRequest.model_validate_json(Path(args.request).read_bytes())
        authorization = LiveAuthorization.model_validate_json(Path(args.authorization).read_bytes())
        policy = CapturePolicy.model_validate_json(Path(args.policy).read_bytes())
        with SQLiteStore(Path(args.store)) as store:
            provider = DataForSEOObservationProvider(
                store, store, HttpsTransport(Credentials.from_environment(), authorization), policy
            )
            result = provider.capture(request)
            if result.status != "succeeded":
                print(
                    json.dumps(
                        {
                            "status": "failed",
                            "request_id": request.id,
                            "error": result.error.code if result.error else "capture_failed",
                        }
                    )
                )
                return 1
            original = require(result)
        with SQLiteStore(Path(args.store)) as store:
            replayed = require(replay_capture(store, store, request.id))
            if original != replayed:
                raise AcquisitionError("replay_mismatch")
            receipt = load_receipt(store, request.id)
            print(
                json.dumps(
                    {
                        "status": "succeeded",
                        "observation_id": original.id,
                        "raw_artifact_id": original.raw_artifact_id,
                        "provider_request_id": original.provider_request_id,
                        "usage": receipt.usage.model_dump(mode="json"),
                    }
                )
            )
            usage = receipt.usage.data
            if usage is None or usage.cost is None:
                return 2  # Unknown billing must not be reported as a verified budget result.
            return 0 if usage.cost <= authorization.cost_ceiling_usd else 2
    except (AcquisitionError, PersistenceError, StorageInitializationError) as error:
        print(json.dumps({"status": "failed", "error": error.detail.code}))
        return 1
    except (ValueError, OSError):
        print(json.dumps({"status": "failed", "error": "invalid_live_check_configuration"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
