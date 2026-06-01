"""Unit tests for core kernel functionality."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.kernel import Kernel, create_default_kernel


class TestKernelInitialization:
    """Tests for Kernel initialization."""

    def test_kernel_http_raises_before_context_manager(self):
        """Test that accessing .http before entering context raises RuntimeError."""
        kernel = Kernel()
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = kernel.http

    def test_kernel_initializes_empty_plugin_registry(self):
        """Test that Kernel starts with empty plugin registry."""
        kernel = Kernel()
        assert kernel._plugins == {}
        assert kernel.get("nonexistent") is None


class TestPluginRegistration:
    """Tests for plugin registration."""

    def test_register_adds_plugin(self):
        """Test that register adds plugin to registry."""
        kernel = Kernel()
        mock_plugin = MagicMock()

        kernel.register("test_plugin", mock_plugin)

        assert "test_plugin" in kernel._plugins
        assert kernel.get("test_plugin") is mock_plugin

    def test_register_sets_kernel_on_plugin(self):
        """Test that register sets kernel attribute on plugin."""
        kernel = Kernel()
        mock_plugin = MagicMock()

        kernel.register("test_plugin", mock_plugin)

        assert mock_plugin.kernel is kernel

    def test_register_overwrites_existing_plugin(self):
        """Test that register overwrites existing plugin with same name."""
        kernel = Kernel()
        mock_plugin_1 = MagicMock()
        mock_plugin_2 = MagicMock()

        kernel.register("test_plugin", mock_plugin_1)
        kernel.register("test_plugin", mock_plugin_2)

        assert kernel.get("test_plugin") is mock_plugin_2

    def test_getitem_raises_keyerror_for_missing(self):
        """Test that __getitem__ raises KeyError for missing plugin."""
        kernel = Kernel()
        with pytest.raises(KeyError):
            kernel["nonexistent"]

    def test_get_returns_none_for_missing(self):
        """Test that get returns None for missing plugin."""
        kernel = Kernel()
        result = kernel.get("nonexistent")
        assert result is None

    def test_get_does_not_accept_default_arg(self):
        """Kernel.get() takes only the name — no default parameter in current API."""
        kernel = Kernel()
        # The current implementation only takes `name`, so passing a second arg raises TypeError
        with pytest.raises(TypeError):
            kernel.get("nonexistent", object())


class TestCreateDefaultKernel:
    """Tests for create_default_kernel factory function."""

    @pytest.mark.asyncio
    async def test_creates_kernel_with_all_plugins(self):
        """Test that all expected plugins are registered."""
        async with await create_default_kernel() as kernel:
            expected_plugins = [
                "auth",
                "book",
                "chapters",
                "assets",
                "html_processor",
                "epub",
                "pdf",
                "output",
                "system",
                "downloader",
            ]
            for plugin_name in expected_plugins:
                assert kernel.get(plugin_name) is not None, f"Plugin '{plugin_name}' not registered"

    @pytest.mark.asyncio
    async def test_plugins_have_kernel_reference(self):
        """Test that all registered plugins have kernel reference."""
        async with await create_default_kernel() as kernel:
            for plugin_name, plugin in kernel._plugins.items():
                assert plugin.kernel is kernel, f"Plugin '{plugin_name}' missing kernel reference"

    @pytest.mark.asyncio
    async def test_http_client_is_initialized_inside_context(self):
        """Test that HTTP client is available inside the async context."""
        from core.http_client import HttpClient

        async with await create_default_kernel() as kernel:
            assert isinstance(kernel.http, HttpClient)


class TestKernelEdgeCases:
    """Edge case tests for Kernel."""

    def test_register_plugin_with_no_kernel_attr_uses_setattr(self):
        """Test registering a MagicMock plugin that accepts attribute setting."""
        kernel = Kernel()
        mock_plugin = MagicMock()

        # MagicMock accepts setattr, so this should work fine
        kernel.register("mock_plugin", mock_plugin)
        assert kernel.get("mock_plugin") is mock_plugin

    def test_register_with_none_name(self):
        """Test registering with None as name."""
        kernel = Kernel()
        mock_plugin = MagicMock()

        # Should work, though not recommended
        kernel.register(None, mock_plugin)

        assert kernel.get(None) is mock_plugin

    def test_multiple_kernels_isolated(self):
        """Test that multiple kernels have isolated plugin registries."""
        kernel_1 = Kernel()
        kernel_2 = Kernel()

        mock_plugin_1 = MagicMock()
        mock_plugin_2 = MagicMock()

        kernel_1.register("test", mock_plugin_1)
        kernel_2.register("test", mock_plugin_2)

        assert kernel_1.get("test") is mock_plugin_1
        assert kernel_2.get("test") is mock_plugin_2
        assert kernel_1.get("test") is not kernel_2.get("test")
