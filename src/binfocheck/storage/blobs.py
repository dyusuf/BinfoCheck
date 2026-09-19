"""POSIX local blobs: digest-only names, pinned directory handles, atomic publication."""

import os
import stat
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from binfocheck.domain.text import ArtifactRef

from .codec import digest
from .errors import StorageError

DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


@contextmanager
def directory(parent: int, name: str, *, create: bool) -> Generator[int]:
    if create:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent)
        except FileExistsError:
            pass
    handle = os.open(name, DIRECTORY_FLAGS, dir_fd=parent)
    try:
        yield handle
    finally:
        os.close(handle)


class ContentAddressedFiles:
    def __init__(self, root: Path) -> None:
        self._root = os.open(root, DIRECTORY_FLAGS)

    @contextmanager
    def _leaf(self, ref: ArtifactRef, *, create: bool) -> Generator[int]:
        # Even internal callers cannot introduce path components through forged models.
        ref = ArtifactRef.model_validate_json(ref.model_dump_json(warnings="error"))
        with (
            directory(self._root, "artifacts", create=create) as artifacts,
            directory(artifacts, ref.access, create=create) as access,
            directory(access, "sha256", create=create) as hashes,
            directory(hashes, ref.sha256[:2], create=create) as leaf,
        ):
            yield leaf

    @staticmethod
    def _read(leaf: int, name: str) -> bytes:
        handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=leaf)
        with os.fdopen(handle, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise StorageError("storage_corrupt")
            return stream.read()

    def read(self, ref: ArtifactRef) -> bytes:
        try:
            with self._leaf(ref, create=False) as leaf:
                content = self._read(leaf, ref.sha256)
        except FileNotFoundError as error:
            raise StorageError("artifact_data_missing") from error
        if digest(content) != ref.sha256:
            raise StorageError("artifact_hash_mismatch")
        return content

    def put(self, ref: ArtifactRef, content: bytes) -> None:
        if digest(content) != ref.sha256:
            raise StorageError("artifact_hash_mismatch")
        with self._leaf(ref, create=True) as leaf:
            try:
                existing = self._read(leaf, ref.sha256)
            except FileNotFoundError:
                pass
            else:
                if existing != content:
                    raise StorageError("artifact_hash_mismatch")
                return
            temporary = ".tmp-" + uuid4().hex
            handle = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=leaf,
            )
            try:
                with os.fdopen(handle, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    os.link(
                        temporary,
                        ref.sha256,
                        src_dir_fd=leaf,
                        dst_dir_fd=leaf,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    if self._read(leaf, ref.sha256) != content:
                        raise StorageError("artifact_hash_mismatch") from None
                os.fsync(leaf)
            finally:
                try:
                    os.unlink(temporary, dir_fd=leaf)
                except OSError:
                    # A handled cleanup failure must not hide the original failure.
                    pass

    def close(self) -> None:
        os.close(self._root)
