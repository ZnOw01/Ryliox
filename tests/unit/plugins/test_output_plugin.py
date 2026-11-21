from __future__ import annotations

import os
import shutil
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from plugins.output import OutputPlugin

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


def test_validate_dir_creates_missing_directory(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    target = tmp_path / "new-output"

    valid, message, resolved = plugin.validate_dir(target)

    assert valid is True
    assert message == "Directory is valid"
    assert resolved == target
    assert target.exists()
    assert target.is_dir()


def test_validate_dir_rejects_path_outside_authorized_root(tmp_path: Path):
    root = tmp_path / "allowed"
    root.mkdir()
    plugin = OutputPlugin(authorized_root=root)

    valid, message, resolved = plugin.validate_dir(tmp_path / "outside")

    assert valid is False
    assert "authorized output root" in message
    assert resolved is None


def test_create_book_dir_creates_expected_structure(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)

    book_dir = plugin.create_book_dir(
        output_dir=tmp_path,
        book_id="demo-book",
        title="A Demo Book",
        authors=["Author One"],
    )

    assert book_dir.exists()
    assert (book_dir / "OEBPS").is_dir()
    assert (book_dir / ".book_id").read_text(encoding="utf-8") == "demo-book"


def test_create_book_dir_uses_unique_suffix_for_collisions(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)

    first = plugin.create_book_dir(
        output_dir=tmp_path,
        book_id="book-1",
        title="Repeated Title",
        authors=None,
    )
    second = plugin.create_book_dir(
        output_dir=tmp_path,
        book_id="book-2",
        title="Repeated Title",
        authors=None,
    )

    assert first != second
    assert first.name == "repeated-title"
    assert second.name == "repeated-title-2"


def _build_staged_book(
    plugin: OutputPlugin, output_dir: Path, job_id: str, name: str, book_id: str
) -> tuple[Path, Path]:
    staging = plugin.create_staging_dir(output_dir=output_dir, job_id=job_id)
    staged_book = staging / name
    (staged_book / "OEBPS").mkdir(parents=True)
    (staged_book / "OEBPS" / "chapter.xhtml").write_text("<html/>", encoding="utf-8")
    (staged_book / ".book_id").write_text(book_id, encoding="utf-8")
    return staging, staged_book


def test_create_staging_dir_creates_dir_under_staging_root(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)

    staging = plugin.create_staging_dir(output_dir=tmp_path, job_id="job-abc")

    assert staging == tmp_path / ".ryliox-staging" / "job-abc"
    assert staging.is_dir()
    assert (tmp_path / ".ryliox-staging").is_dir()


def test_create_staging_dir_makes_unique_dir_for_duplicate_job_id(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)

    first = plugin.create_staging_dir(output_dir=tmp_path, job_id="job-abc")
    second = plugin.create_staging_dir(output_dir=tmp_path, job_id="job-abc")

    assert first == tmp_path / ".ryliox-staging" / "job-abc"
    assert second == tmp_path / ".ryliox-staging" / "job-abc-2"
    assert first.is_dir()
    assert second.is_dir()


def test_create_staging_dir_rejects_traversal_job_id(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)

    for bad in ("../../outside", "..", ".", "a/b", "", "sub/.."):
        with pytest.raises(ValueError):
            plugin.create_staging_dir(output_dir=tmp_path, job_id=bad)

    assert not (tmp_path / ".ryliox-staging").exists()
    assert not (tmp_path.parent / "outside").exists()


def test_create_staging_dir_rejects_output_dir_outside_root(tmp_path: Path):
    root = tmp_path / "allowed"
    root.mkdir()
    plugin = OutputPlugin(authorized_root=root)

    with pytest.raises(ValueError):
        plugin.create_staging_dir(output_dir=tmp_path, job_id="job-1")


def test_publish_staged_dir_moves_complete_book_into_output(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    _, staged_book = _build_staged_book(plugin, tmp_path, "job-1", "demo-book", "book-1")

    published = plugin.publish_staged_dir(staged_book, output_dir=tmp_path, book_id="book-1")

    assert published == tmp_path / "demo-book"
    assert published.is_dir()
    assert (published / "OEBPS" / "chapter.xhtml").read_text(encoding="utf-8") == "<html/>"
    assert (published / ".book_id").read_text(encoding="utf-8") == "book-1"
    assert not staged_book.exists()


def test_publish_staged_dir_preserves_legacy_output_dir(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    legacy = tmp_path / "demo-book"
    legacy.mkdir()
    (legacy / "notes.txt").write_text("keep me", encoding="utf-8")

    _, staged_book = _build_staged_book(plugin, tmp_path, "job-1", "demo-book", "book-1")
    published = plugin.publish_staged_dir(staged_book, output_dir=tmp_path, book_id="book-1")

    assert legacy.is_dir()
    assert (legacy / "notes.txt").read_text(encoding="utf-8") == "keep me"
    assert published == tmp_path / "demo-book-2"
    assert (published / ".book_id").read_text(encoding="utf-8") == "book-1"
    assert not staged_book.exists()


def test_publish_staged_dir_preserves_foreign_file_at_target_name(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    foreign = tmp_path / "demo-book"
    foreign.write_text("foreign file", encoding="utf-8")

    _, staged_book = _build_staged_book(plugin, tmp_path, "job-1", "demo-book", "book-1")
    published = plugin.publish_staged_dir(staged_book, output_dir=tmp_path, book_id="book-1")

    assert foreign.read_text(encoding="utf-8") == "foreign file"
    assert published == tmp_path / "demo-book-2"
    assert not staged_book.exists()


def test_publish_staged_dir_fails_atomically_when_rename_raises(tmp_path: Path, monkeypatch):
    plugin = OutputPlugin(authorized_root=tmp_path)
    existing = tmp_path / "demo-book"
    existing.mkdir()
    (existing / "notes.txt").write_text("keep", encoding="utf-8")

    _, staged_book = _build_staged_book(plugin, tmp_path, "job-1", "demo-book", "book-1")

    def failing_rename(*_args, **_kwargs):
        raise OSError("simulated rename failure")

    monkeypatch.setattr(os, "rename", failing_rename)

    with pytest.raises(OSError):
        plugin.publish_staged_dir(staged_book, output_dir=tmp_path, book_id="book-1")

    assert staged_book.is_dir()
    assert (staged_book / "OEBPS" / "chapter.xhtml").exists()
    assert (existing / "notes.txt").read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "demo-book-2").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == [".ryliox-staging", "demo-book"]


def test_publish_staged_dir_republishes_same_book_under_suffix(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    _, first_staged = _build_staged_book(plugin, tmp_path, "job-1", "demo-book", "book-1")
    first = plugin.publish_staged_dir(first_staged, output_dir=tmp_path, book_id="book-1")
    assert first == tmp_path / "demo-book"

    _, second_staged = _build_staged_book(plugin, tmp_path, "job-2", "demo-book", "book-1")
    second = plugin.publish_staged_dir(second_staged, output_dir=tmp_path, book_id="book-1")

    assert second == tmp_path / "demo-book-2"
    assert second.is_dir()
    assert (second / ".book_id").read_text(encoding="utf-8") == "book-1"
    assert (first / "OEBPS" / "chapter.xhtml").read_text(encoding="utf-8") == "<html/>"
    assert not second_staged.exists()


def test_publish_staged_dir_refuses_path_outside_staging(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    foreign = tmp_path / "not-staged"
    foreign.mkdir()
    (foreign / "file.txt").write_text("x", encoding="utf-8")

    with pytest.raises(ValueError):
        plugin.publish_staged_dir(foreign, output_dir=tmp_path, book_id="book-1")

    assert foreign.is_dir()
    assert (foreign / "file.txt").read_text(encoding="utf-8") == "x"


def test_publish_staged_dir_requires_same_filesystem(tmp_path: Path, monkeypatch):
    plugin = OutputPlugin(authorized_root=tmp_path)
    _, staged_book = _build_staged_book(plugin, tmp_path, "job-1", "demo-book", "book-1")
    real_fstat = os.fstat
    output_ino = tmp_path.stat().st_ino

    def fake_fstat(fd):
        st = real_fstat(fd)
        if st.st_ino == output_ino:
            return SimpleNamespace(st_dev=st.st_dev + 1, st_mode=st.st_mode, st_ino=st.st_ino)
        return st

    monkeypatch.setattr(os, "fstat", fake_fstat)

    with pytest.raises(OSError):
        plugin.publish_staged_dir(staged_book, output_dir=tmp_path, book_id="book-1")

    assert staged_book.is_dir()
    assert not (tmp_path / "demo-book").exists()


def test_publish_staged_dir_refuses_staging_outside_authorized_root(tmp_path: Path):
    root = tmp_path / "allowed"
    root.mkdir()
    plugin = OutputPlugin(authorized_root=root)
    staged_book = tmp_path / "other" / ".ryliox-staging" / "job-1" / "demo-book"
    (staged_book / "OEBPS").mkdir(parents=True)
    (staged_book / ".book_id").write_text("book-1", encoding="utf-8")

    with pytest.raises(ValueError):
        plugin.publish_staged_dir(staged_book, output_dir=root, book_id="book-1")

    assert staged_book.is_dir()
    assert (staged_book / ".book_id").read_text(encoding="utf-8") == "book-1"
    assert not (root / "demo-book").exists()


def test_publish_staged_dir_refuses_staging_not_under_associated_root(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    foreign_staging = tmp_path / "other-output" / ".ryliox-staging"
    _, staged_book = _build_staged_book(
        plugin, tmp_path / "other-output", "job-1", "demo-book", "book-1"
    )

    with pytest.raises(ValueError):
        plugin.publish_staged_dir(staged_book, output_dir=tmp_path, book_id="book-1")

    assert foreign_staging.is_dir()
    assert staged_book.is_dir()
    assert not (tmp_path / "demo-book").exists()


def test_publish_staged_dir_refuses_symlink_resolving_outside_root(tmp_path: Path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    plugin = OutputPlugin(authorized_root=root)
    staging_root = root / ".ryliox-staging"
    staging_root.mkdir()
    link = staging_root / "job-1"
    link.symlink_to(outside, target_is_directory=True)
    staged = link / "demo-book"

    with pytest.raises(ValueError):
        plugin.publish_staged_dir(staged, output_dir=root, book_id="book-1")

    assert outside.is_dir()
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_cleanup_staging_deletes_only_managed_staging(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    staging = plugin.create_staging_dir(output_dir=tmp_path, job_id="job-1")
    (staging / "partial.txt").write_text("half-done", encoding="utf-8")
    (staging / "sub").mkdir()

    plugin.cleanup_staging(staging)
    plugin.cleanup_staging(staging)

    assert not staging.exists()
    assert not (tmp_path / ".ryliox-staging" / "job-1").exists()


def test_cleanup_staging_accepts_nested_authorized_output_dir(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    output_dir = tmp_path / "downloads" / "books"
    staging = plugin.create_staging_dir(output_dir=output_dir, job_id="job-nested")
    (staging / "partial.txt").write_text("partial", encoding="utf-8")

    plugin.cleanup_staging(staging)

    assert not staging.exists()


def test_cleanup_staging_refuses_arbitrary_paths(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    innocent = output_dir / "innocent"
    innocent.mkdir()
    (innocent / "data.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError):
        plugin.cleanup_staging(innocent)
    with pytest.raises(ValueError):
        plugin.cleanup_staging(output_dir)
    with pytest.raises(ValueError):
        plugin.cleanup_staging(output_dir / ".ryliox-staging")

    assert innocent.is_dir()
    assert (innocent / "data.txt").read_text(encoding="utf-8") == "keep"


def test_cleanup_staging_refuses_staging_outside_authorized_root(tmp_path: Path):
    root = tmp_path / "allowed"
    root.mkdir()
    plugin = OutputPlugin(authorized_root=root)
    victim = tmp_path / "other" / ".ryliox-staging" / "job-1"
    victim.mkdir(parents=True)
    (victim / "data.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError):
        plugin.cleanup_staging(victim)

    assert victim.is_dir()
    assert (victim / "data.txt").read_text(encoding="utf-8") == "keep"


def test_cleanup_staging_refuses_nested_subdir_of_job(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    staging = plugin.create_staging_dir(output_dir=tmp_path, job_id="job-1")
    nested = staging / "sub"
    nested.mkdir()
    (nested / "data.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError):
        plugin.cleanup_staging(nested)

    assert nested.is_dir()
    assert (nested / "data.txt").read_text(encoding="utf-8") == "keep"
    assert staging.is_dir()


def test_cleanup_staging_refuses_symlink_resolving_outside_root(tmp_path: Path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    plugin = OutputPlugin(authorized_root=root)
    staging_root = root / ".ryliox-staging"
    staging_root.mkdir()
    link = staging_root / "job-1"
    link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError):
        plugin.cleanup_staging(link)

    assert outside.is_dir()
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert link.is_symlink()


def test_create_staging_dir_refuses_symlinked_staging_root(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    link = tmp_path / ".ryliox-staging"
    link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError):
        plugin.create_staging_dir(output_dir=tmp_path, job_id="job-1")

    assert outside.is_dir()
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not (outside / "job-1").exists()
    assert link.is_symlink()


def test_create_book_dir_preserves_symlink_at_candidate_name(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    link = tmp_path / "repeated-title"
    link.symlink_to(outside, target_is_directory=True)

    book_dir = plugin.create_book_dir(
        output_dir=tmp_path,
        book_id="book-1",
        title="Repeated Title",
        authors=None,
    )

    assert book_dir == tmp_path / "repeated-title-2"
    assert (book_dir / "OEBPS").is_dir()
    assert (book_dir / ".book_id").read_text(encoding="utf-8") == "book-1"
    assert link.is_symlink()
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_publish_staged_dir_refuses_symlinked_staging_root(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    link = tmp_path / ".ryliox-staging"
    link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError):
        plugin.publish_staged_dir(
            link / "job-1" / "demo-book", output_dir=tmp_path, book_id="book-1"
        )

    assert outside.is_dir()
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert link.is_symlink()


def test_cleanup_staging_refuses_symlinked_staging_root(tmp_path: Path):
    plugin = OutputPlugin(authorized_root=tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    link = tmp_path / ".ryliox-staging"
    link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError):
        plugin.cleanup_staging(link / "job-1")

    assert outside.is_dir()
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert link.is_symlink()


def test_cleanup_staging_does_not_delete_outside_on_concurrent_symlink_swap(
    tmp_path: Path, monkeypatch
):
    plugin = OutputPlugin(authorized_root=tmp_path)
    staging = plugin.create_staging_dir(output_dir=tmp_path, job_id="job-race")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")

    real_rmtree = shutil.rmtree
    swapped = False

    def racing_rmtree(name, **kwargs):
        nonlocal swapped
        if not swapped:
            swapped = True
            staging.rmdir()
            staging.symlink_to(outside, target_is_directory=True)
        return real_rmtree(name, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", racing_rmtree)

    with pytest.raises(Exception):
        plugin.cleanup_staging(staging)

    assert (outside / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert staging.is_symlink()
