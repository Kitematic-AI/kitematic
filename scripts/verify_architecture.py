#!/usr/bin/env python3
"""AST-based architecture verification for Kitematic.

Uses only Python stdlib (ast, inspect, pathlib, os, sys).
No external dependencies.

Usage:
    python scripts/verify_architecture.py [project_root]
"""

import ast
import importlib
import inspect
import sys
from pathlib import Path
from typing import NamedTuple

# ─── Configuration ──────────────────────────────────────────────────────────

# Layer rules: which layers can import which
# Key: source layer, Value: set of allowed target layers
LAYER_ALLOWED_IMPORTS: dict[str, set[str]] = {
    "core":           {"core"},
    "kernel":         {"core", "kernel"},
    "control_plane":  {"core", "kernel", "control_plane"},
    "agents":         {"core", "kernel", "agents", "ai_gateway"},
    "ai_gateway":     {"core", "ai_gateway"},
    "infrastructure": {"core", "infrastructure"},
    "api":            {"core", "kernel", "control_plane", "api"},
    "config":         {"core", "config"},
    "runtime":        {"core", "kernel", "runtime"},
    "services":       {"core", "kernel", "control_plane", "services"},
}

# Forbidden imports in specific directories (module prefix → layer)
FORBIDDEN_IMPORTS: dict[str, set[str]] = {
    "control_plane": {
        "sqlite3", "psycopg", "psycopg2", "sqlalchemy",
        "pymongo", "redis",
        "requests", "httpx", "aiohttp", "urllib", "http.client", "websockets",
    },
}

# Known ABC → implementation pairs (class name → (abc_module_path, impl_module_path))
KNOWN_ABC_IMPLEMENTATIONS: list[tuple[str, str, str | None]] = [
    ("TemplateRepository",  "control_plane/registry", "control_plane/registry"),
    ("InstanceRepository",  "control_plane/registry", "control_plane/registry"),
    ("PolicyEvaluator",     "core/policies", "control_plane/policy"),
    ("Orchestrator",        "control_plane/orchestrator", None),
]

# Known contract pairs for signature consistency checking
# (abc_module, abc_class, impl_module, impl_class)
KNOWN_CONTRACTS: list[tuple[str, str, str, str]] = [
    (
        "control_plane.registry.template_repository",
        "TemplateRepository",
        "control_plane.registry.memory_template_repository",
        "MemoryTemplateRepository",
    ),
    (
        "control_plane.registry.instance_repository",
        "InstanceRepository",
        "control_plane.registry.memory_instance_repository",
        "MemoryInstanceRepository",
    ),
    (
        "core.policies.evaluator",
        "PolicyEvaluator",
        "control_plane.policy.engine",
        "PolicyEngine",
    ),
]


# ─── Data types ─────────────────────────────────────────────────────────────

class CheckResult(NamedTuple):
    name: str
    passed: bool
    details: list[str]


# ─── Helpers ────────────────────────────────────────────────────────────────

def discover_python_files(root: Path, exclude_tests: bool = False) -> list[Path]:
    """Find all .py files, excluding __pycache__ and .pyc."""
    files: list[Path] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        parts = rel.parts
        if "__pycache__" in parts:
            continue
        if exclude_tests and parts[0] == "tests":
            continue
        files.append(path)
    return sorted(files)


def get_layer(filepath: Path, root: Path) -> str | None:
    """Determine the layer for a file based on its path."""
    rel = filepath.relative_to(root)
    parts = rel.parts
    if parts[0] in ("core", "kernel", "control_plane", "agents",
                     "ai_gateway", "infrastructure", "api", "config",
                     "runtime", "services"):
        return parts[0]
    return None


def extract_imports(filepath: Path) -> list[str]:
    """Extract all import names from a Python file using AST."""
    try:
        tree = ast.parse(filepath.read_text(), filename=str(filepath))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def is_project_import(module: str, root: Path) -> bool:
    """Check if a module import belongs to the project."""
    parts = module.split(".")
    return parts[0] in ("runtime", "services")


def classify_import(module: str) -> str | None:
    """Classify which layer an import belongs to."""
    parts = module.split(".")
    if parts[0] == "runtime":
        return "runtime"
    if parts[0] == "services":
        return "services"
    return None


# ─── Checks ─────────────────────────────────────────────────────────────────

def check_dependency_direction(root: Path) -> CheckResult:
    """Check 1: Dependency direction — runtime must not import services."""
    violations: list[str] = []
    for filepath in discover_python_files(root, exclude_tests=True):
        layer = get_layer(filepath, root)
        if layer is None:
            continue
        imports = extract_imports(filepath)
        for imp in imports:
            if not is_project_import(imp, root):
                continue
            target_layer = classify_import(imp)
            if target_layer is None:
                continue
            allowed = LAYER_ALLOWED_IMPORTS.get(layer, set())
            if target_layer not in allowed:
                rel = filepath.relative_to(root)
                violations.append(f"  {rel}\n    imports {imp}")
    return CheckResult(
        name="Dependency Direction",
        passed=len(violations) == 0,
        details=violations,
    )


def check_forbidden_imports(root: Path) -> CheckResult:
    """Check 3: Forbidden imports in specific directories."""
    violations: list[str] = []
    for filepath in discover_python_files(root, exclude_tests=True):
        rel = filepath.relative_to(root)
        rel_str = str(rel)
        for dir_pattern, forbidden in FORBIDDEN_IMPORTS.items():
            if dir_pattern in rel.parts:
                imports = extract_imports(filepath)
                for imp in imports:
                    for fb in forbidden:
                        if imp == fb or imp.startswith(fb + "."):
                            violations.append(f"  {rel_str}\n    imports '{imp}' (forbidden)")
    return CheckResult(
        name="Forbidden Imports",
        passed=len(violations) == 0,
        details=violations,
    )


def check_import_cycles(root: Path) -> CheckResult:
    """Check 4: Import cycles in project modules (runtime + services)."""
    project_files = discover_python_files(root, exclude_tests=True)
    graph: dict[str, list[str]] = {}

    for filepath in project_files:
        layer = get_layer(filepath, root)
        if layer is None:
            continue
        rel = str(filepath.relative_to(root))
        imports = extract_imports(filepath)
        deps: list[str] = []
        for imp in imports:
            if is_project_import(imp, root):
                # Map module to file path
                parts = imp.split(".")
                candidate = root / Path("/".join(parts)).with_suffix(".py")
                candidate_pkg = root / Path("/".join(parts)) / "__init__.py"
                if candidate.exists():
                    deps.append(str(candidate.relative_to(root)))
                elif candidate_pkg.exists():
                    deps.append(str(candidate_pkg.relative_to(root)))
        graph[rel] = deps

    # DFS cycle detection
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in graph}
    cycle_path: list[str] = []

    def dfs(node: str) -> bool:
        color[node] = GRAY
        cycle_path.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                cycle_path.append(neighbor)
                return True
            if color[neighbor] == WHITE and dfs(neighbor):
                return True
        cycle_path.pop()
        color[node] = BLACK
        return False

    found_cycle = False
    for node in list(graph.keys()):
        if color[node] == WHITE:
            if dfs(node):
                found_cycle = True
                break

    details: list[str] = []
    if found_cycle:
        details.append(f"  Cycle detected: {' → '.join(cycle_path)}")

    return CheckResult(
        name="Import Cycles",
        passed=not found_cycle,
        details=details,
    )


def check_interface_compliance(root: Path) -> CheckResult:
    """Check 5: Known ABCs have implementations with all abstract methods."""
    violations: list[str] = []
    for abc_name, abc_dir, impl_dir in KNOWN_ABC_IMPLEMENTATIONS:
        abc_path = root / abc_dir
        if not abc_path.exists():
            continue

        # Find the ABC class
        abc_class = None
        for py_file in abc_path.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        base_name = ""
                        if isinstance(base, ast.Name):
                            base_name = base.id
                        elif isinstance(base, ast.Attribute):
                            base_name = base.attr
                        if base_name == "ABC" or any(
                            b.id == "ABC" if isinstance(b, ast.Name) else False
                            for b in (node.bases if isinstance(node.bases, list) else [])
                        ):
                            if node.name == abc_name:
                                abc_class = node
                                break

        if abc_class is None:
            continue

        # Check if implementation exists
        if impl_dir is None:
            continue
        impl_path = root / impl_dir
        if not impl_path.exists():
            violations.append(f"  {abc_name}: no implementation directory {impl_dir}")
            continue

        # Check if any class in impl_dir inherits from the ABC
        found_impl = False
        for py_file in impl_path.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        base_name = ""
                        if isinstance(base, ast.Name):
                            base_name = base.id
                        elif isinstance(base, ast.Attribute):
                            base_name = base.attr
                        if base_name == abc_name:
                            found_impl = True
                            # Check abstract methods
                            abstract_methods = set()
                            for item in ast.walk(abc_class):
                                if isinstance(item, ast.FunctionDef):
                                    for dec in item.decorator_list:
                                        if isinstance(dec, ast.Name) and dec.id == "abstractmethod":
                                            abstract_methods.add(item.name)

                            impl_methods = {m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
                            missing = abstract_methods - impl_methods
                            if missing:
                                violations.append(f"  {abc_name} → {node.name}: missing {missing}")
                            break

        if not found_impl:
            violations.append(f"  {abc_name}: no implementation found in {impl_dir}")

    return CheckResult(
        name="Interface Compliance",
        passed=len(violations) == 0,
        details=violations,
    )


def check_contract_consistency(root: Path) -> CheckResult:
    """Check 6: Contract consistency — signatures must match between ABC and implementation."""
    violations: list[str] = []

    for abc_mod_path, abc_cls, impl_mod_path, impl_cls in KNOWN_CONTRACTS:
        try:
            # Ensure project root is on sys.path
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            abc_mod = importlib.import_module(abc_mod_path)
            abc_class = getattr(abc_mod, abc_cls)
        except (ImportError, AttributeError) as e:
            violations.append(f"  {abc_mod_path}.{abc_cls}: import failed ({e})")
            continue

        try:
            impl_mod = importlib.import_module(impl_mod_path)
            impl_class = getattr(impl_mod, impl_cls)
        except (ImportError, AttributeError) as e:
            violations.append(f"  {impl_mod_path}.{impl_cls}: import failed ({e})")
            continue

        abstract_methods = getattr(abc_class, '__abstractmethods__', set())
        for method_name in abstract_methods:
            abc_method = getattr(abc_class, method_name, None)
            impl_method = getattr(impl_class, method_name, None)

            if abc_method is None:
                violations.append(f"  {abc_cls}.{method_name}: ABC method not found")
                continue

            if impl_method is None:
                violations.append(f"  {impl_cls}.{method_name}: implementation not found")
                continue

            try:
                abc_sig = inspect.signature(abc_method)
                impl_sig = inspect.signature(impl_method)

                if str(abc_sig) != str(impl_sig):
                    violations.append(
                        f"  {impl_cls}.{method_name}: signature mismatch\n"
                        f"    ABC:   {abc_sig}\n"
                        f"    Found: {impl_sig}"
                    )
            except (ValueError, TypeError) as e:
                violations.append(f"  {impl_cls}.{method_name}: signature inspection failed ({e})")

    return CheckResult(
        name="Contract Consistency",
        passed=len(violations) == 0,
        details=violations,
    )


def check_package_boundaries(root: Path) -> CheckResult:
    """Check 7: No imports from __pycache__ or _private folders."""
    # Standard library dunder modules are not private packages
    _DUNDER_WHITELIST = {"__future__", "__main__", "__init__"}
    violations: list[str] = []
    for filepath in discover_python_files(root, exclude_tests=True):
        imports = extract_imports(filepath)
        for imp in imports:
            parts = imp.split(".")
            for part in parts:
                if part.startswith("_") and part not in _DUNDER_WHITELIST:
                    rel = filepath.relative_to(root)
                    violations.append(f"  {rel}\n    imports '{imp}' (private package)")
                    break
    return CheckResult(
        name="Package Boundaries",
        passed=len(violations) == 0,
        details=violations,
    )


def check_hygiene(root: Path) -> CheckResult:
    """Check 8: No pass/TODO/NotImplementedError in non-test, non-script files."""
    violations: list[str] = []

    for filepath in discover_python_files(root, exclude_tests=True):
        rel = filepath.relative_to(root)
        parts = rel.parts
        # Skip scripts directory
        if parts[0] == "scripts":
            continue
        # Skip __init__.py files (often have pass)
        if filepath.name == "__init__.py":
            continue

        try:
            tree = ast.parse(filepath.read_text())
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            # Check for pass statements
            if isinstance(node, ast.Pass):
                violations.append(f"  {rel}:{node.lineno}")
                continue

            # Check for string literals that are TODO/FIXME
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for pat in ["TODO", "FIXME", "HACK"]:
                    if pat in node.value:
                        violations.append(f"  {rel}:{node.lineno} — contains '{pat}'")
                        break

            # Check for NotImplementedError
            if isinstance(node, ast.Raise) and node.exc:
                if isinstance(node.exc, ast.Call):
                    func = node.exc.func
                    if isinstance(func, ast.Name) and func.id == "NotImplementedError":
                        violations.append(f"  {rel}:{node.lineno}")

    return CheckResult(
        name="Hygiene",
        passed=len(violations) == 0,
        details=violations,
    )


def check_layer_isolation(root: Path) -> CheckResult:
    """Check 2: runtime must not import services (subset of dependency direction)."""
    violations: list[str] = []
    for filepath in discover_python_files(root, exclude_tests=True):
        rel = filepath.relative_to(root)
        parts = rel.parts
        if parts[0] != "runtime":
            continue
        imports = extract_imports(filepath)
        for imp in imports:
            if imp.startswith("services"):
                violations.append(f"  {rel}\n    imports '{imp}'")
    return CheckResult(
        name="Layer Isolation",
        passed=len(violations) == 0,
        details=violations,
    )


# ─── Main ───────────────────────────────────────────────────────────────────

def run_verification(root: Path) -> tuple[list[CheckResult], int]:
    """Run all checks. Returns (results, exit_code)."""
    checks = [
        check_dependency_direction,
        check_layer_isolation,
        check_forbidden_imports,
        check_import_cycles,
        check_interface_compliance,
        check_contract_consistency,
        check_package_boundaries,
        check_hygiene,
    ]

    results: list[CheckResult] = []
    for check_fn in checks:
        results.append(check_fn(root))

    failed = sum(1 for r in results if not r.passed)
    exit_code = 1 if failed > 0 else 0
    return results, exit_code


def print_report(results: list[CheckResult]) -> None:
    """Print CI-friendly report."""
    print("Architecture Verification Report")
    print("================================")
    print()

    for i, r in enumerate(results, 1):
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {i}. {r.name}")
        for detail in r.details:
            print(f"    {detail}")

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print()
    print(f"Summary: {passed}/{total} passed")


def main() -> int:
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
    else:
        root = Path(__file__).resolve().parent.parent

    if not root.exists():
        print(f"Error: {root} does not exist", file=sys.stderr)
        return 1

    results, exit_code = run_verification(root)
    print_report(results)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
