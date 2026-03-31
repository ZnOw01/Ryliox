"""Feature flags management for the application."""
from typing import Dict, Set, Any
import os

# Flag definitions with descriptions
FEATURE_FLAGS_CONFIG: Dict[str, Any] = {
    "enable_new_ui": {
        "description": "Enables the redesigned user interface",
        "default": False,
        "category": "ui"
    },
    "enable_batch_downloads": {
        "description": "Allows downloading multiple books at once",
        "default": False,
        "category": "downloads"
    },
    "enable_advanced_search": {
        "description": "Enables advanced search features including fuzzy search and filters",
        "default": True,
        "category": "search"
    },
    "enable_pwa": {
        "description": "Enables Progressive Web App features",
        "default": True,
        "category": "ui"
    },
    "enable_dark_mode": {
        "description": "Enables dark mode toggle in UI",
        "default": True,
        "category": "ui"
    },
    "enable_keyboard_shortcuts": {
        "description": "Enables keyboard shortcuts help modal",
        "default": True,
        "category": "accessibility"
    },
    "enable_a11y_improvements": {
        "description": "Enables advanced accessibility features",
        "default": True,
        "category": "accessibility"
    },
}


class FeatureFlags:
    """Centralized feature flags management."""
    
    def __init__(self) -> None:
        self._flags: Dict[str, bool] = {}
        self._load_from_environment()
    
    def _load_from_environment(self) -> None:
        """Load feature flags from environment variables."""
        for flag_name, config in FEATURE_FLAGS_CONFIG.items():
            env_var = f"FEATURE_{flag_name.upper()}"
            env_value = os.getenv(env_var)
            
            if env_value is not None:
                # Parse boolean from string
                self._flags[flag_name] = env_value.lower() in ("true", "1", "yes", "on")
            else:
                self._flags[flag_name] = config["default"]
    
    def is_enabled(self, flag_name: str) -> bool:
        """Check if a feature flag is enabled.
        
        Args:
            flag_name: The name of the feature flag.
            
        Returns:
            True if the flag is enabled, False otherwise.
        """
        return self._flags.get(flag_name, False)
    
    def get_all(self) -> Dict[str, bool]:
        """Get all feature flags and their states.
        
        Returns:
            Dictionary mapping flag names to their boolean states.
        """
        return self._flags.copy()
    
    def get_config(self) -> Dict[str, Dict[str, Any]]:
        """Get the full configuration for all flags.
        
        Returns:
            Dictionary with flag configurations including descriptions.
        """
        result = {}
        for flag_name, config in FEATURE_FLAGS_CONFIG.items():
            result[flag_name] = {
                **config,
                "enabled": self._flags.get(flag_name, False)
            }
        return result
    
    def set_flag(self, flag_name: str, enabled: bool) -> None:
        """Set a feature flag state (for runtime toggling).
        
        Args:
            flag_name: The name of the feature flag.
            enabled: The new state of the flag.
        """
        if flag_name in FEATURE_FLAGS_CONFIG:
            self._flags[flag_name] = enabled
    
    def get_flags_by_category(self, category: str) -> Dict[str, bool]:
        """Get all flags for a specific category.
        
        Args:
            category: The category to filter by.
            
        Returns:
            Dictionary of flag names to states for the category.
        """
        return {
            name: self._flags.get(name, False)
            for name, config in FEATURE_FLAGS_CONFIG.items()
            if config.get("category") == category
        }


# Global instance
feature_flags = FeatureFlags()


def is_feature_enabled(flag_name: str) -> bool:
    """Convenience function to check if a feature is enabled.
    
    Args:
        flag_name: The name of the feature flag.
        
    Returns:
        True if the feature is enabled.
    """
    return feature_flags.is_enabled(flag_name)
