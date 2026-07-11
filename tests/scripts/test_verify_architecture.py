"""Tests for the architecture verification script itself.

Uses tempfile.TemporaryDirectory to create isolated mock projects.
No files are created in the real project tree.
"""

import tempfile
from pathlib import Path

import pytest
from scripts.verify_architecture import run_verification, check_hygiene


def _create_mock_project(root: Path, files: dict[str, str]) -> None:
    """Create mock Python files in a temporary directory."""
    for rel_path, content in files.items():
        filepath = root / rel_path
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content)


class TestVerifyCleanProject:
    def test_clean_project_passes(self, tmp_path: Path) -> None:
        _create_mock_project(tmp_path, {
            "runtime/domain/model.py": "class Model:\n    def __init__(self): self.x = 1",
            "services/service.py": "from runtime.domain.model import Model",
            "tests/test_model.py": "def test_pass(): pass",
        })
        results, exit_code = run_verification(tmp_path)
        assert exit_code == 0
        assert all(r.passed for r in results)


class TestVerifyViolationDetected:
    def test_runtime_imports_services_fails(self, tmp_path: Path) -> None:
        _create_mock_project(tmp_path, {
            "runtime/domain/model.py": "from services.service import Service",
            "services/service.py": "class Service: pass",
        })
        results, exit_code = run_verification(tmp_path)
        assert exit_code == 1
        dep_check = [r for r in results if r.name == "Dependency Direction"][0]
        assert not dep_check.passed

    def test_forbidden_import_fails(self, tmp_path: Path) -> None:
        _create_mock_project(tmp_path, {
            "services/control_plane/engine.py": "import sqlite3",
        })
        results, exit_code = run_verification(tmp_path)
        assert exit_code == 1
        forbidden_check = [r for r in results if r.name == "Forbidden Imports"][0]
        assert not forbidden_check.passed

    def test_hygiene_violation_fails(self, tmp_path: Path) -> None:
        _create_mock_project(tmp_path, {
            "runtime/domain/model.py": 'x = "TODO: implement"',
        })
        results, exit_code = run_verification(tmp_path)
        assert exit_code == 1
        hygiene_check = [r for r in results if r.name == "Hygiene"][0]
        assert not hygiene_check.passed

    def test_not_implemented_error_fails(self, tmp_path: Path) -> None:
        _create_mock_project(tmp_path, {
            "runtime/domain/model.py": "raise NotImplementedError()",
        })
        results, exit_code = run_verification(tmp_path)
        assert exit_code == 1
        hygiene_check = [r for r in results if r.name == "Hygiene"][0]
        assert not hygiene_check.passed

    def test_pass_in_non_init_fails(self, tmp_path: Path) -> None:
        _create_mock_project(tmp_path, {
            "runtime/domain/model.py": "pass",
        })
        results, exit_code = run_verification(tmp_path)
        assert exit_code == 1
        hygiene_check = [r for r in results if r.name == "Hygiene"][0]
        assert not hygiene_check.passed


class TestHygieneExclusions:
    def test_scripts_directory_excluded(self, tmp_path: Path) -> None:
        _create_mock_project(tmp_path, {
            "scripts/tool.py": "x = 1  # TODO: implement later",
        })
        result = check_hygiene(tmp_path)
        assert result.passed

    def test_init_files_excluded(self, tmp_path: Path) -> None:
        _create_mock_project(tmp_path, {
            "runtime/domain/__init__.py": "pass",
        })
        result = check_hygiene(tmp_path)
        assert result.passed

    def test_test_files_excluded(self, tmp_path: Path) -> None:
        _create_mock_project(tmp_path, {
            "tests/test_model.py": "raise NotImplementedError",
        })
        result = check_hygiene(tmp_path)
        assert result.passed
