"""
Configuration management for NeuroMem SDK.
"""

import yaml
from pathlib import Path
from typing import Dict, Any


class NeuroMemConfig:
    """
    Configuration loader for NeuroMem.
    
    Loads and provides access to configuration from YAML files.
    
    Example config structure:
        neuromem:
          model:
            embedding: text-embedding-3-large
            consolidation_llm: gpt-4.1-mini
          storage:
            database:
              type: postgres
              url: postgresql://user:pass@localhost:5432/neuromem
            vector_store:
              type: chroma
              collection: user_memory
          memory:
            decay_enabled: true
            consolidation_interval: 10
            max_active_memories: 50
    """
    
    def __init__(self, path: str):
        """
        Initialize configuration from a YAML file.
        
        Args:
            path: Path to the configuration YAML file
        """
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        
        with open(config_path, 'r') as f:
            self.raw = yaml.safe_load(f)
        
        if "neuromem" not in self.raw:
            raise ValueError("Invalid configuration: missing 'neuromem' root key")
    
    def model(self) -> Dict[str, Any]:
        """
        Get model configuration.
        
        Returns:
            Dictionary with model settings (embedding model, LLM for consolidation, etc.)
        """
        return self.raw["neuromem"].get("model", {})
    
    def storage(self) -> Dict[str, Any]:
        """
        Get storage configuration.
        
        Returns:
            Dictionary with storage backend settings
        """
        return self.raw["neuromem"].get("storage", {})
    
    def memory(self) -> Dict[str, Any]:
        """
        Get memory system configuration.
        
        Returns:
            Dictionary with memory behavior settings
        """
        return self.raw["neuromem"].get("memory", {})
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key path.
        
        Args:
            key: Dot-separated key path (e.g., "model.embedding")
            default: Default value if key not found
        
        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self.raw.get("neuromem", {})
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        
        return value if value is not None else default


def create_default_config(path: str = "neuromem.yaml"):
    """
    Create a default configuration file.
    
    Args:
        path: Path where to create the config file
    """
    default_config = {
        "neuromem": {
            "model": {
                "embedding": "text-embedding-3-large",
                "consolidation_llm": "gpt-4o-mini"
            },
            "storage": {
                "database": {
                    "type": "memory",
                    "url": None
                },
                "vector_store": {
                    "type": "memory",
                    "collection": "user_memory"
                },
                "cache": {
                    "type": "memory",
                    "ttl_seconds": 3600
                }
            },
            "memory": {
                "decay_enabled": True,
                "consolidation_interval": 10,
                "max_active_memories": 50,
                "episodic_retention_days": 30,
                "min_confidence_threshold": 0.3
            }
        }
    }
    
    with open(path, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
    
    print(f"Created default configuration at {path}")
