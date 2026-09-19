# Shared storage (T11A)

`MemoryStore()` and `SQLiteStore(Path(root))` implement the existing T00
`RecordStore` and `ArtifactStore` protocols. Both support `close()` and context
management. `SQLiteStore` uses Python's standard-library SQLite and filesystem
facilities; there is no service or additional dependency.

```python
from pathlib import Path

from binfocheck.domain.storage import IdRequest
from binfocheck.storage import SQLiteStore

with SQLiteStore(Path("/configured/private/store")) as store:
    result = store.get_record(IdRequest(id="obs-1"))
    # Inspect result.status and result.error before using result.value.
```

The root is trusted operator configuration, not request input. The implementation
targets POSIX local filesystems (the repository's Linux/Ubuntu environment).
New roots are created with mode `0700`. Existing roots must have no group/other
permission bits (normally `0700`); otherwise opening fails with
`StorageInitializationError` code `insecure_storage_permissions` before SQLite is
opened or created. Storage does not silently chmod an existing directory. The
operator must secure the configured root before retrying, because SQLite contains
record/text data as well as artifact metadata. Permissions must remain private
throughout use; this startup check is not user authorization or an ACL audit.
Each instance owns a SQLite connection and is used from its creating thread;
separate instances support bounded concurrent writers. The default busy timeout
is one second, configurable between zero and sixty seconds. There are no automatic
write retries. Retry the same immutable operation after a transient/uncertain
failure; do not create a new ID merely to retry.

## Records and history

All record kinds, including artifact references, share one ID namespace. New IDs
insert; identical canonical content succeeds without duplicate rows; different
content under an existing ID returns `immutable_id_conflict`. Decisions and reviews
use this same primitive, including when passed to generic `put_record`. New versions
and superseding reviews require new IDs. There is no update/delete operation.

The version-one codec revalidates models, emits UTF-8 JSON with sorted object keys,
explicit defaults/nulls and compact separators, and records a SHA-256 hash. It never
normalizes text, reorders arrays, removes missing values, or equates arbitrary JSON
integers and floating-point values. Reads verify the hash and revalidate. Returned
models do not share mutable children with stored or submitted models.

Writes perform local contract validation, not full graph validation: the shared
records contain cycles and can arrive in any order. Call domain `validate_links`
on a complete assembled set when linked-record validation is required. T11A adds
neither a batch protocol nor downstream selection/review-state logic.

## Artifacts

Internal layout:

```text
root/
  store.sqlite3
  artifacts/{restricted|shareable_fixture}/sha256/<first-two-hex>/<sha256>
```

`storage_key` is metadata, never a path. Paths use only revalidated hash/access
fields and fixed components; artifact traversal uses pinned directory descriptors
and rejects symlinks. The root and SQLite files must remain under trusted operator
control; this is not a defense against an administrator replacing the store itself.
`restricted` is metadata/physical grouping, not user authorization. T12/D10 owns
authentication and access control. No artifact download interface is provided.

Strict base64 decoding and SHA-256 verification precede writes. Temporary files are
created exclusively in the destination directory, written fully, flushed/synced,
and atomically published with a no-replace hard link. Existing blobs are compared
before reuse. Database payload metadata commits after publication. Handled failures
roll back metadata and attempt temporary-file cleanup. Identical bytes deduplicate
within an access class. Empty bytes are a valid artifact, not missing data.

SQLite and filesystem writes are not a distributed transaction: a failure may
leave an unreferenced complete blob, safely reusable on retry. There is no garbage
collection, process-kill/power-loss guarantee, or network-filesystem guarantee.
Close/reopen persistence and handled write failures are tested.

`put_record(ArtifactRef)` may precede the bytes. Such metadata remains retrievable,
but `get_artifact` returns `artifact_data_missing` until a successful matching
`put_artifact`. Missing or corrupt files are failures, not empty successes. An
identical explicit retry can restore missing bytes, but never replaces corrupt
existing bytes silently.

Callers must remove credentials before constructing payloads and record transport
redactions. Storage does not inspect arbitrary content for every possible secret
or rewrite hashed bytes. Errors contain fixed codes/messages, never payloads,
raw SQL, credentials, or internal paths.

## Listing and schema

Listing uses insertion sequence, not timestamp or lexicographic ID. Limits are
1–1000. Filters select kind and direct run ownership; a `RunManifest` belongs to
its own ID. Other inputs are not assigned to runs by graph traversal. A valid query
with no matches succeeds with an empty page; missing ID lookup returns `not_found`.

Versioned, opaque base64 cursors carry store identity, exact filters, last position,
and the initial high-water sequence. Later inserts are excluded from that traversal;
page size may change, and cursors survive reopen. Structure, identity, filters,
range, and the matching continuation position are checked. Cursors are deliberately
unsigned and must not be used as authorization or tamper-proof tokens (T12/D10).

SQLite indexes cover ID, kind/sequence, run/sequence, and run/kind/sequence. JSON is
authoritative and indexed metadata is checked on record reads. `application_id`
identifies this store; `user_version=1` identifies its storage schema. Codec version
1 is separate from domain wire schema `1` / validation revision `1.1`. Initialization
is transactional and only applies to empty databases. Foreign/unsupported schemas
are rejected; there are no speculative migrations or historic-record rewrites.

## Failures and verification

Operations return T00 `Outcome` failures. Main codes: `not_found`,
`artifact_data_missing`, `immutable_id_conflict`, `invalid_record`,
`invalid_artifact_base64`, `artifact_hash_mismatch`, `invalid_cursor`,
`storage_busy`, `storage_io_error`, `storage_corrupt`, and `store_closed`.
Known SQLite busy/locked failures are retryable; validation/conflicts are not.
Opening fails with `StorageInitializationError.detail`, including foreign/unsupported
schema, unsafe path, and invalid configuration codes. Concrete close/context-manager
methods are lifecycle helpers, outside the Outcome-returning T00 protocols.

Run `uv run --offline --locked pytest tests/storage`, then the full checks in the
repository CI. Tests use the existing synthetic linked fixture and synthetic bytes
matching its artifact hashes; no provider calls, credentials, or live artifacts.
