"""Coverage gate: verify total coverage >= threshold AND no per-package regression.

Usage:
    python scripts/check_coverage.py <coverage.xml> <threshold_percent>

Reads the Cobertura XML coverage report and checks:
  1. Line-rate >= threshold (overall)
  2. No package's line-rate drops below its recorded baseline

Baseline is stored in .coverage-baseline.json next to this script.
If baseline doesn't exist, it's created from the current report.
"""

import json
import sys
import xml.etree.ElementTree as ET

BASELINE_FILE = ".coverage-baseline.json"


def parse_packages(xml_path: str) -> dict[str, float]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    packages: dict[str, float] = {}
    for pkg in root.findall(".//package"):
        name = pkg.get("name", "")
        rate = float(pkg.get("line-rate", 0))
        packages[name] = rate
    return packages


def runtime_packages(packages: dict[str, float]) -> dict[str, float]:
    return {k: v for k, v in packages.items() if "kitematic_runtime" in k}


def load_baseline() -> dict[str, float]:
    try:
        with open(BASELINE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_baseline(packages: dict[str, float]) -> None:
    with open(BASELINE_FILE, "w") as f:
        json.dump(packages, f, indent=2)
    print(f"Baseline saved: {BASELINE_FILE}")


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python scripts/check_coverage.py <coverage.xml> <threshold>")
        sys.exit(1)

    xml_path = sys.argv[1]
    threshold = float(sys.argv[2])
    packages = parse_packages(xml_path)
    rp = runtime_packages(packages)

    overall = sum(rp.values()) / len(rp) if rp else 0.0
    print(f"Runtime coverage: {overall:.2%} (threshold: {threshold:.0f}%)")

    if overall < (threshold / 100):
        print(f"FAIL: Runtime coverage {overall:.2%} < {threshold:.0f}%")
        sys.exit(1)

    baseline = load_baseline()
    if not baseline:
        save_baseline(rp)
        print("No prior baseline — created from current report.")
        sys.exit(0)

    failed = False
    for pkg, rate in sorted(rp.items()):
        prev = baseline.get(pkg)
        if prev is not None and rate < prev - 0.005:  # 0.5% tolerance
            print(
                f"FAIL: {pkg}: {rate:.2%} dropped from baseline {prev:.2%} "
                f"({(prev - rate) * 100:.1f}% regression)"
            )
            failed = True

    if failed:
        print("Per-package coverage regression detected.")
        sys.exit(1)

    print("All coverage gates passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
