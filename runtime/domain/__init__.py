"""Domain models — the core abstractions of the Kitematic system.

This package is the innermost layer. It must NOT import from:
- services/
- infrastructure/
- any external database library

It MAY import from:
- runtime/contracts/
- standard library dataclasses, enum, typing
"""
