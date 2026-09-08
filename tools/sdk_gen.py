import os
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
STUB_OUTPUT_DIR = os.getcwd() + "/src/engine_sdk/src/animaengine"


# -----------------------------
# UTILITIES
# -----------------------------

def remove_invalid_imports_from_stubs():
    """Remove imports pointing to modules that aren't present in the generated stubs."""
    root = Path(STUB_OUTPUT_DIR)

    for path in root.rglob("*.pyi"):
        source = path.read_text()
        tree = ast.parse(source)
        lines = source.splitlines(keepends=True)

        new_lines = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                # Only handle relative imports, e.g. `from .utils import ...`
                if node.level > 0:
                    package_dir = path.parent

                    # Resolve relative import level
                    for _ in range(node.level - 1):
                        package_dir = package_dir.parent

                    module = node.module or ""

                    module_path = package_dir / Path(*module.split("."))

                    # A generated module can be either:
                    #   foo.pyi
                    # or:
                    #   foo/__init__.pyi
                    exists = (
                        module_path.with_suffix(".pyi").exists()
                        or (module_path / "__init__.pyi").exists()
                    )

                    if not exists:
                        print(f"Removing invalid import: {node.module} in {path}")
                        continue

            new_lines.extend(lines[node.lineno - 1:node.end_lineno])

        path.write_text("".join(new_lines))

def run_stubgen():
    cmd = ["stubgen", "-o", STUB_OUTPUT_DIR, "--include-docstrings"]

    for module in API_MODULES:
        cmd.extend(["-m", module])

    for package in API_PACKAGES:
        cmd.extend(["-p", package])

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

from pathlib import Path
import shutil

SRC_ROOT = Path(os.getcwd()) / "src" / "engine_sdk" / "src"

def flatten_generated_package():
    for pkg_dir in SRC_ROOT.iterdir():
        if not pkg_dir.is_dir():
            continue

        nested = pkg_dir / pkg_dir.name
        if not nested.is_dir():
            continue

        # Move every generated file up one level
        for item in nested.iterdir():
            shutil.move(str(item), pkg_dir / item.name)

        shutil.rmtree(nested)

# -----------------------------
# MAIN WORKFLOW
# -----------------------------

def main():
    workspace_root = Path.cwd()
    print(f"Workspace root: {workspace_root}")

    # Step 3: Run stubgen
    run_stubgen()
    remove_invalid_imports_from_stubs()
    flatten_generated_package()

    print("\nDone! Clean API stubs are in:", STUB_OUTPUT_DIR)


if __name__ == "__main__":
    main()