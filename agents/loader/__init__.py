"""Plugin loader — lifecycle management for all plugin types.

The loader is responsible for:
  - Discovering installed plugins (tools, frameworks, models)
  - Validating plugin manifests
  - Installing and removing plugins
  - Bridging plugins into the kernel through policy + registry
"""
