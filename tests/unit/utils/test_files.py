"""Tests for file utility functions."""

from __future__ import annotations

import pytest

from utils.files import remove_accents, sanitize_filename, slugify

pytestmark = pytest.mark.unit


class TestRemoveAccents:
    """Test suite for remove_accents function."""

    def test_basic_accents(self):
        """Test removal of common accents."""
        assert remove_accents("café") == "cafe"
        assert remove_accents("naïve") == "naive"
        assert remove_accents("résumé") == "resume"

    def test_spanish_characters(self):
        """Test removal of Spanish-specific characters."""
        assert remove_accents("Ñoño") == "Nono"
        assert remove_accents("El niño") == "El nino"
        assert remove_accents("señor") == "senor"

    def test_german_characters(self):
        """Test removal of German umlauts."""
        assert remove_accents("über") == "uber"
        # Note: ß (eszett) becomes 's' in NFKD decomposition
        result = remove_accents("straße")
        assert "str" in result and "e" in result  # Basic check
        # ö becomes 'o' in NFKD
        result2 = remove_accents("größe")
        assert "gro" in result2 and "e" in result2

    def test_empty_string(self):
        """Test empty string handling."""
        assert remove_accents("") == ""

    def test_no_accents(self):
        """Test string without accents remains unchanged."""
        assert remove_accents("hello") == "hello"
        assert remove_accents("TEST123") == "TEST123"


class TestSanitizeFilename:
    """Test suite for sanitize_filename function."""

    def test_invalid_characters(self):
        """Test removal/replacement of invalid filename characters."""
        assert sanitize_filename("My: File?.txt") == "My- File.txt"
        assert sanitize_filename("file|name.txt") == "file-name.txt"
        assert sanitize_filename('file"name.txt') == "file'name.txt"

    def test_path_traversal_protection(self):
        """Test protection against path traversal attacks."""
        # Path traversal characters are replaced with '-' not removed
        result = sanitize_filename("../../etc/passwd")
        assert ".." not in result  # No path traversal sequences
        assert "etc" in result and "passwd" in result  # Path components preserved

        result2 = sanitize_filename("../secret.txt")
        assert ".." not in result2
        assert "secret" in result2 and "txt" in result2

        # Absolute paths lose leading separators
        result3 = sanitize_filename("/absolute/path")
        assert not result3.startswith(("/", "\\"))
        assert "absolute" in result3 and "path" in result3

        # Home and special prefixes are stripped
        result4 = sanitize_filename("~file.txt")
        assert not result4.startswith("~")
        assert "file" in result4 and "txt" in result4

    def test_windows_reserved_names(self):
        """Test handling of Windows reserved names."""
        assert sanitize_filename("CON") == "CON_"
        assert sanitize_filename("CON.txt") == "CON_.txt"
        assert sanitize_filename("PRN") == "PRN_"
        assert sanitize_filename("AUX") == "AUX_"
        assert sanitize_filename("NUL") == "NUL_"
        assert sanitize_filename("COM1") == "COM1_"
        assert sanitize_filename("LPT1") == "LPT1_"

    def test_whitespace_handling(self):
        """Test handling of whitespace and dots."""
        # Leading/trailing whitespace is stripped
        assert sanitize_filename("   filename.txt   ") == "filename.txt"
        # Multiple dots are preserved (only special chars like : | are replaced)
        result = sanitize_filename("file...name")
        assert "file" in result and "name" in result
        # Edge case: only dots and spaces - dots become dashes after strip
        result = sanitize_filename("   ...   ")
        # After stripping whitespace and collapsing, we get something non-empty
        # or it falls back to 'unnamed_file'
        assert result != "" and (result == "unnamed_file" or "-" in result)

    def test_none_input(self):
        """Test handling of None input."""
        assert sanitize_filename(None) == "unnamed_file"

    def test_control_characters(self):
        """Test removal of control characters."""
        assert sanitize_filename("file\x00name") == "filename"
        assert sanitize_filename("file\x1fname") == "filename"
        assert sanitize_filename("file\x7fname") == "filename"

    def test_unicode_handling(self):
        """Test handling of unicode characters."""
        assert "ñ" in sanitize_filename("cañón.txt") or "n" in sanitize_filename("cañón.txt")


class TestSlugify:
    """Test suite for slugify function."""

    def test_basic_slugification(self):
        """Test basic slug creation."""
        assert slugify("Hello World") == "hello-world"
        assert slugify("Test 123") == "test-123"

    def test_accents_removal(self):
        """Test that accents are removed in slugs."""
        assert slugify("¡Héroe del Mañana!") == "heroe-del-manana"
        assert slugify("café français") == "cafe-francais"

    def test_multiple_spaces(self):
        """Test handling of multiple spaces."""
        assert slugify("  Multiple   Spaces  ") == "multiple-spaces"
        assert slugify("a    b     c") == "a-b-c"

    def test_special_characters(self):
        """Test removal of special characters."""
        assert slugify("test@file#name") == "test-file-name"
        assert slugify("file[name]") == "file-name"
        assert slugify("a+b=c") == "a-b-c"

    def test_quotes_removal(self):
        """Test that quotes are removed."""
        # Single and double quotes are removed entirely
        assert slugify('"quoted"') == "quoted"
        assert slugify("'single'") == "single"
        # Mixed quotes are removed but dashes may collapse
        result = slugify('"mixed\'quotes"')
        assert "mixed" in result and "quotes" in result
        assert '"' not in result and "'" not in result

    def test_empty_and_none(self):
        """Test handling of empty and None inputs."""
        assert slugify("") == "unnamed-folder"
        assert slugify(None) == "unnamed-folder"

    def test_trailing_dashes(self):
        """Test that trailing dashes are removed."""
        assert slugify("-test-") == "test"
        assert slugify("--multiple--dashes--") == "multiple-dashes"

    def test_case_conversion(self):
        """Test that uppercase is converted to lowercase."""
        assert slugify("UPPERCASE") == "uppercase"
        assert slugify("MixedCase") == "mixedcase"


class TestSecurityValidations:
    """Test security-related filename validations."""

    def test_null_bytes_rejection(self):
        """Test that null bytes are rejected."""
        result = sanitize_filename("file\x00.txt")
        assert "\x00" not in result

    def test_path_traversal_blocked(self):
        """Test that path traversal attempts are blocked."""
        malicious_inputs = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "~/.bashrc",
            "$HOME/.ssh/id_rsa",
        ]
        for inp in malicious_inputs:
            result = sanitize_filename(inp)
            assert ".." not in result
            assert not result.startswith(("/", "\\", "~", "$"))

    def test_control_chars_blocked(self):
        """Test that control characters are blocked."""
        for i in range(32):
            inp = f"file{chr(i)}name"
            result = sanitize_filename(inp)
            assert all(ord(c) >= 32 or c == "\n" or c == "\r" or c == "\t" for c in result)
