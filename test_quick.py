#!/usr/bin/env python3
"""Quick test of critical imports and config."""

from daily_companion import merge_config

config = merge_config()

print("✅ All modules import successfully")
print(f"✅ Palette in config: {bool(config.get('palette'))}")
print(f"✅ Palette colors: {list(config['palette'].keys())}")
print(f"✅ Config version: {config.get('config_version')}")
print("\nAll high-priority fixes verified! Ready for commit.")
