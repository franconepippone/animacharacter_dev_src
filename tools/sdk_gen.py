
import ast
import subprocess
import sys
from pathlib import Path
from typing import Set, List


# -----------------------------
# CONFIGURATION
# -----------------------------

# Your API entrypoints (modules that define the public API)
API_MODULES = [
    "hardware_mng.abstract_hw_controller",
]

API_PACKAGES = [
    "animaengine",
    "hardware_mng.databus"
]

# Where to output stubs
STUB_OUTPUT_DIR = "stubs_out"


# -----------------------------
# UTILITIES
# -----------------------------


def run_stubgen():
    """Run stubgen on a list of Python files."""
    cmd = ["stubgen", "-o", STUB_OUTPUT_DIR, "--include-docstrings"]
    cmd.extend(f"-m {M}" for M in API_MODULES)
    cmd.extend(f"-p {P}" for P in API_PACKAGES)
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def clean_imports():
    """Remove unused imports from generated stubs."""
    cmd = [
        "autoflake",
        "--remove-all-unused-imports",
        "--recursive",
        "--in-place",
        STUB_OUTPUT_DIR,
    ]
    print("Cleaning imports:", " ".join(cmd))
    subprocess.run(cmd, check=True)


# -----------------------------
# MAIN WORKFLOW
# -----------------------------

def main():
    workspace_root = Path.cwd()
    print(f"Workspace root: {workspace_root}")

    # Step 3: Run stubgen
    run_stubgen()

    # Step 4: Clean unused imports
    clean_imports()

    print("\nDone! Clean API stubs are in:", STUB_OUTPUT_DIR)


if __name__ == "__main__":
    main()