#!/usr/bin/env python3
"""Validate and test disposable copies with mock providers, without credentials."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
    ).decode().split("\0")
    with tempfile.TemporaryDirectory(prefix="ha-cloudflare-test-") as tmp:
        stage = Path(tmp) / "source"
        stage.mkdir()
        for name in set(names):
            source = ROOT / name
            if not name or not source.is_file() or source.is_symlink():
                continue
            if ".terraform" in source.parts or ".tfstate" in source.name or source.name.endswith((".tfvars", ".tfvars.json", ".tfplan")):
                raise SystemExit("Private Terraform input or state found among source files")
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
        config = Path(tmp) / "empty.tfrc"
        config.write_text("")
        environment = {k: v for k, v in os.environ.items()
                       if not k.startswith(("TF_", "CLOUDFLARE_"))}
        environment.update(TF_CLI_CONFIG_FILE=str(config), TF_INPUT="0", TF_IN_AUTOMATION="1")
        for relative in (".", "modules/publication", "examples/shared-tunnel"):
            directory = stage / relative
            for args in (("fmt", "-check", "-recursive"),
                         ("init", "-backend=false", "-input=false", "-no-color"),
                         ("validate", "-no-color")):
                subprocess.run(["terraform", *args], cwd=directory, env=environment, check=True)
            if (directory / "tests").is_dir():
                # Every test file defines mock_provider; no real API apply occurs.
                subprocess.run(["terraform", "test", "-no-color"], cwd=directory, env=environment, check=True)


if __name__ == "__main__":
    main()
