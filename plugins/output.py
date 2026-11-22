"""Output directory management plugin.

Every destructive, creation or publication operation is anchored to the
authorized root through directory descriptors.  Relative components are opened
with ``O_DIRECTORY | O_NOFOLLOW`` so a symlink introduced anywhere between the
root and the target fails closed instead of being followed.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
from pathlib import Path

import config
from plugins.base import Plugin
from utils import slugify

STAGING_DIRNAME = ".ryliox-staging"

_DIRECTORY_FLAGS = os.O_DIRECTORY | os.O_NOFOLLOW

_RMTREE_AVOIDS_SYMLINK_ATTACKS = shutil.rmtree.avoids_symlink_attacks


def _mkdir_unique(dir_fd: int, base: str) -> str:
    """Exclusively create a directory under ``dir_fd`` with a free suffix.

    Retries with a numeric ``-N`` suffix until ``mkdir`` succeeds; returns
    the name actually created.
    """
    candidate = base
    counter = 2
    while True:
        try:
            os.mkdir(candidate, dir_fd=dir_fd)
            return candidate
        except FileExistsError:
            candidate = f"{base}-{counter}"
            counter += 1


class OutputPlugin(Plugin):
    """Manages output directories and file organization."""

    def __init__(self, authorized_root: Path | None = None) -> None:
        self._authorized_root = Path(authorized_root or config.OUTPUT_ROOT).expanduser().resolve()
        self._root_identity: tuple[int, int] | None = None
        try:
            st = self._authorized_root.stat()
        except OSError:
            pass
        else:
            self._root_identity = (st.st_dev, st.st_ino)

    def get_default_dir(self) -> Path:
        """Return the default output directory from config."""
        return config.OUTPUT_DIR

    def validate_dir(self, path: str | Path | None) -> tuple[bool, str, Path | None]:
        """Validate that a directory is writable and confined to the output root."""
        if path is None:
            return True, "Using default directory", self.get_default_dir()

        path = self._normalize(Path(path))
        try:
            path.relative_to(self._authorized_root)
        except ValueError:
            return (
                False,
                f"Directory must be inside authorized output root: {self._authorized_root}",
                None,
            )

        try:
            fd = self._open_or_create_dir(path)
        except (ValueError, OSError) as exc:
            return False, f"Cannot create directory: {exc}", None

        try:
            try:
                test_fd = os.open(".write_test", os.O_WRONLY | os.O_CREAT, dir_fd=fd)
            except OSError:
                return False, "Directory is not writable", None
            os.close(test_fd)
            os.unlink(".write_test", dir_fd=fd)
        finally:
            os.close(fd)

        return True, "Directory is valid", path

    def create_book_dir(
        self,
        output_dir: Path,
        book_id: str,
        title: str,
        authors: list[str] | None = None,
    ) -> Path:
        """Create a book output directory with conflict resolution.

        The book directory is created with an exclusive ``mkdir`` under a
        descriptor anchored to the authorized root, so a pre-existing entry or
        a concurrent symlink at the target name is never followed: existing
        outputs are preserved and a free numeric suffix is used instead.
        """
        output_dir = self._normalize(Path(output_dir))
        self._ensure_under_root(output_dir)

        folder_title = (title or "").strip()
        if not folder_title and authors:
            folder_title = f"Book by {authors[0]}"
        if not folder_title:
            folder_title = book_id

        folder_name = slugify(folder_title)

        output_fd = self._open_under_root(output_dir)
        try:
            book_name = self._create_book_dir_fd(output_fd, folder_name, book_id)
        finally:
            os.close(output_fd)
        return output_dir / book_name

    def create_staging_dir(self, output_dir: Path, job_id: str) -> Path:
        """Create a unique staging directory for a job under ``.ryliox-staging``.

        The returned directory lives at ``<output_dir>/.ryliox-staging/<job_id>``
        and is only ever used as a private build area. ``job_id`` must be a
        single path component so callers cannot traverse outside the staging
        root.  A symlink already present at ``.ryliox-staging`` is never
        followed.
        """
        output_dir = self._normalize(Path(output_dir))
        self._ensure_under_root(output_dir)
        job_id = self._validate_job_id(job_id)

        output_fd = self._open_or_create_dir(output_dir)
        try:
            with contextlib.suppress(FileExistsError):
                os.mkdir(STAGING_DIRNAME, dir_fd=output_fd)
            try:
                staging_fd = os.open(STAGING_DIRNAME, _DIRECTORY_FLAGS, dir_fd=output_fd)
            except OSError as exc:
                raise ValueError(
                    f"Refusing to use non-directory or symlinked {STAGING_DIRNAME} under {output_dir}"
                ) from exc
            try:
                return self._unique_dir_fd(staging_fd, job_id, output_dir / STAGING_DIRNAME)
            finally:
                os.close(staging_fd)
        finally:
            os.close(output_fd)

    def publish_staged_dir(self, staged_book_dir: Path, output_dir: Path, book_id: str) -> Path:
        """Atomically move a completed staged book dir into ``output_dir``.

        The staged directory is renamed atomically (``os.rename`` anchored to
        directory descriptors) into the target, so ``output_dir`` only ever
        observes complete books — never partial builds.  The staged directory
        must live at ``<output_dir>/.ryliox-staging/<job>/<name>`` with every
        component opened ``O_NOFOLLOW``; anything else is refused.  The target
        name is reserved with an exclusive ``mkdir``, so an existing entry —
        including a previously published copy of the same book — is left
        untouched and the new book is published under a numeric suffix instead.
        """
        staged_book_dir = self._normalize(Path(staged_book_dir))
        output_dir = self._normalize(Path(output_dir))
        self._ensure_under_root(output_dir)
        try:
            rel = staged_book_dir.relative_to(output_dir)
        except ValueError as exc:
            raise ValueError(
                f"Staged book dir is not under output directory: {output_dir}"
            ) from exc

        parts = rel.parts
        if len(parts) != 3 or parts[0] != STAGING_DIRNAME:
            raise ValueError(f"Staged book dir is not under {STAGING_DIRNAME}: {staged_book_dir}")
        job_name, book_name = parts[1], parts[2]
        self._validate_simple_name(job_name, "staging job")
        self._validate_simple_name(book_name, "staged book")

        output_fd = self._open_under_root(output_dir)
        try:
            try:
                staging_fd = os.open(STAGING_DIRNAME, _DIRECTORY_FLAGS, dir_fd=output_fd)
            except OSError as exc:
                raise ValueError(
                    f"Refusing to use non-directory or symlinked {STAGING_DIRNAME} under {output_dir}"
                ) from exc
            try:
                try:
                    job_fd = os.open(job_name, _DIRECTORY_FLAGS, dir_fd=staging_fd)
                except OSError as exc:
                    raise ValueError(
                        f"Staging job is not a real directory or is a symlink: {job_name}"
                    ) from exc
                try:
                    try:
                        src_fd = os.open(book_name, _DIRECTORY_FLAGS, dir_fd=job_fd)
                    except OSError as exc:
                        raise ValueError(
                            f"Staged book is not a real directory or is a symlink: {book_name}"
                        ) from exc
                    try:
                        if not self._same_filesystem(src_fd, output_fd):
                            raise OSError(
                                f"Cannot publish across filesystems: "
                                f"{staged_book_dir} and {output_dir} are on different devices"
                            )
                    finally:
                        os.close(src_fd)

                    target_name = self._reserve_target(output_fd, book_name)
                    try:
                        os.rename(
                            book_name,
                            target_name,
                            src_dir_fd=job_fd,
                            dst_dir_fd=output_fd,
                        )
                    except Exception:
                        with contextlib.suppress(OSError):
                            os.rmdir(target_name, dir_fd=output_fd)
                        raise
                finally:
                    os.close(job_fd)
            finally:
                os.close(staging_fd)
        finally:
            os.close(output_fd)
        return output_dir / target_name

    def cleanup_staging(self, staging_dir: Path) -> None:
        """Idempotently remove a job directory created by this plugin.

        Only a job directory whose immediate parent is a ``.ryliox-staging``
        directory under the authorized root is removed.  Removal is anchored to
        a descriptor of the staging root via ``shutil.rmtree(name,
        dir_fd=parent_fd)``, which never follows symlinks.  The staging root
        itself, nested build content, and paths outside the authorized root
        raise ``ValueError`` and are left intact.
        """
        staging_dir = self._normalize(Path(staging_dir))
        self._validate_cleanup_target(staging_dir)
        if not _RMTREE_AVOIDS_SYMLINK_ATTACKS:
            raise RuntimeError(
                "Refusing to remove staging: shutil.rmtree does not avoid symlink attacks"
            )
        job_name = staging_dir.name
        output_dir = staging_dir.parent.parent

        output_fd = self._open_under_root(output_dir)
        try:
            try:
                staging_fd = os.open(STAGING_DIRNAME, _DIRECTORY_FLAGS, dir_fd=output_fd)
            except OSError as exc:
                raise ValueError(
                    f"Refusing to use non-directory or symlinked {STAGING_DIRNAME} under {output_dir}"
                ) from exc
            try:
                try:
                    st = os.lstat(job_name, dir_fd=staging_fd)
                except FileNotFoundError:
                    return
                if stat.S_ISLNK(st.st_mode):
                    raise ValueError(
                        f"Refusing to clean up a symlinked staging job directory: {staging_dir}"
                    )
                if not stat.S_ISDIR(st.st_mode):
                    raise ValueError(
                        f"Refusing to clean up a non-directory staging job entry: {staging_dir}"
                    )
                shutil.rmtree(job_name, dir_fd=staging_fd)
            finally:
                os.close(staging_fd)
        finally:
            os.close(output_fd)

    def _validate_cleanup_target(self, path: Path) -> None:
        if not self._is_under_root(path):
            raise ValueError(
                f"Refusing to clean up path outside {STAGING_DIRNAME} under "
                f"{self._authorized_root}: {path}"
            )
        if path.parent.name != STAGING_DIRNAME:
            raise ValueError(
                f"Refusing to clean up a path that is not a staging job directory: {path}"
            )

    def _ensure_under_root(self, path: Path) -> None:
        if not self._is_under_root(path):
            raise ValueError(
                f"Output directory is outside authorized root: {self._authorized_root}"
            )

    def _is_under_root(self, path: Path) -> bool:
        return self._is_under(path, self._authorized_root)

    @staticmethod
    def _is_under(path: Path, ancestor: Path) -> bool:
        try:
            path.relative_to(ancestor)
        except ValueError:
            return False
        return True

    @staticmethod
    def _is_simple_name(name: str) -> bool:
        """Whether ``name`` is a non-empty single path component."""
        return bool(name) and name not in {".", ".."} and Path(name).name == name

    @classmethod
    def _validate_job_id(cls, job_id: str) -> str:
        if not cls._is_simple_name(job_id):
            raise ValueError(f"Invalid job_id: {job_id!r}")
        return job_id

    @classmethod
    def _validate_simple_name(cls, name: str, kind: str) -> None:
        if not cls._is_simple_name(name):
            raise ValueError(f"Invalid {kind} name: {name!r}")

    @staticmethod
    def _normalize(path: Path) -> Path:
        return Path(os.path.normpath(path))

    def _root_fd(self) -> int:
        """Open the authorized root, verifying it still matches the cached identity."""
        try:
            st = self._authorized_root.stat()
        except FileNotFoundError:
            # The root is the user's own configured output directory; on a fresh
            # install it does not exist yet, so create it instead of failing.
            try:
                self._authorized_root.mkdir(parents=True, exist_ok=True)
                st = self._authorized_root.stat()
            except OSError as exc:
                raise ValueError(
                    f"Authorized root is not accessible: {self._authorized_root}"
                ) from exc
            if self._root_identity is None:
                self._root_identity = (st.st_dev, st.st_ino)
        except OSError as exc:
            raise ValueError(f"Authorized root is not accessible: {self._authorized_root}") from exc
        identity = (st.st_dev, st.st_ino)
        if self._root_identity is not None and identity != self._root_identity:
            raise ValueError(
                f"Authorized root was replaced or symlinked since initialization: "
                f"{self._authorized_root}"
            )
        try:
            return os.open(self._authorized_root, _DIRECTORY_FLAGS)
        except OSError as exc:
            raise ValueError(
                f"Authorized root is not an accessible directory: {self._authorized_root}"
            ) from exc

    @staticmethod
    def _open_relative(root_fd: int, parts: tuple[str, ...]) -> int:
        """Open the last component of ``parts`` relative to ``root_fd``.

        Every component is opened with ``O_DIRECTORY | O_NOFOLLOW``; a symlink
        or non-directory anywhere along the chain raises ``OSError``.  The
        returned descriptor is the only one left open.
        """
        if not parts:
            raise ValueError("cannot open an empty relative path")
        fd = root_fd
        opened: list[int] = []
        try:
            for part in parts:
                new_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=fd)
                opened.append(new_fd)
                fd = new_fd
        except OSError:
            for item in opened:
                os.close(item)
            raise
        for item in opened[:-1]:
            os.close(item)
        return opened[-1]

    def _open_under_root(self, path: Path) -> int:
        """Open an existing directory under the root, refusing symlinks on the way."""
        try:
            rel = path.relative_to(self._authorized_root)
        except ValueError as exc:
            raise ValueError(f"Path is outside authorized root: {self._authorized_root}") from exc
        root_fd = self._root_fd()
        if not rel.parts:
            return root_fd
        try:
            fd = self._open_relative(root_fd, rel.parts)
        except OSError as exc:
            os.close(root_fd)
            raise ValueError(f"Path traverses a symlink or is not a directory: {path}") from exc
        os.close(root_fd)
        return fd

    def _open_or_create_dir(self, path: Path) -> int:
        """Open ``path`` under the root, creating missing components as needed.

        Creation uses ``os.mkdir(..., dir_fd=...)`` so a component that exists
        as a symlink is never followed — it surfaces as an error instead.
        """
        rel = path.relative_to(self._authorized_root)
        if not rel.parts:
            return self._root_fd()
        root_fd = self._root_fd()
        fd = root_fd
        held: list[int] = []
        try:
            for part in rel.parts:
                try:
                    new_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=fd)
                except OSError:
                    try:
                        os.mkdir(part, dir_fd=fd)
                    except OSError as exc:
                        raise ValueError(f"Cannot create directory component: {part}") from exc
                    new_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=fd)
                held.append(new_fd)
                fd = new_fd
        except OSError:
            for item in held:
                os.close(item)
            os.close(root_fd)
            raise
        for item in held[:-1]:
            os.close(item)
        os.close(root_fd)
        return held[-1]

    def _unique_dir_fd(self, parent_fd: int, base: str, parent_path: Path) -> Path:
        """Create an exclusive directory under ``parent_fd`` with a free suffix."""
        return parent_path / _mkdir_unique(parent_fd, base)

    @staticmethod
    def _create_book_dir_fd(output_fd: int, base: str, book_id: str) -> str:
        """Exclusively create a book directory and its build skeleton.

        The directory and its ``OEBPS`` subtree are created with exclusive
        ``mkdir`` calls and ``.book_id`` with ``O_CREAT | O_EXCL`` under
        descriptors, so a pre-existing entry or a race-introduced symlink at
        any of these names is never followed.  On failure any partially created
        skeleton is removed best-effort before re-raising.
        """
        candidate = _mkdir_unique(output_fd, base)
        book_fd = os.open(candidate, _DIRECTORY_FLAGS, dir_fd=output_fd)
        error: BaseException | None = None
        try:
            try:
                os.mkdir("OEBPS", dir_fd=book_fd)
                meta_fd = os.open(
                    ".book_id", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644, dir_fd=book_fd
                )
                try:
                    os.write(meta_fd, book_id.encode("utf-8"))
                finally:
                    os.close(meta_fd)
            except BaseException as exc:
                error = exc
                with contextlib.suppress(OSError):
                    os.rmdir("OEBPS", dir_fd=book_fd)
                with contextlib.suppress(OSError):
                    os.unlink(".book_id", dir_fd=book_fd)
        finally:
            os.close(book_fd)
        if error is not None:
            with contextlib.suppress(OSError):
                os.rmdir(candidate, dir_fd=output_fd)
            raise error
        return candidate

    def _reserve_target(self, output_fd: int, base: str) -> str:
        """Reserve a free target name under ``output_fd`` with an exclusive ``mkdir``.

        The empty reservation marker makes concurrent publication to the same
        name fail closed instead of silently replacing foreign content; it is
        atomically replaced by the staged directory on rename.
        """
        return _mkdir_unique(output_fd, base)

    @staticmethod
    def _same_filesystem(src_fd: int, dst_fd: int) -> bool:
        return os.fstat(src_fd).st_dev == os.fstat(dst_fd).st_dev

    def get_oebps_dir(self, book_dir: Path) -> Path:
        """Get the OEBPS directory for a book."""
        return book_dir / "OEBPS"

    def get_images_dir(self, book_dir: Path) -> Path:
        """Get the Images directory for a book."""
        return book_dir / "OEBPS" / "Images"
