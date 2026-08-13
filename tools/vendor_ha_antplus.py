#!/usr/bin/env python3
"""Vendor only the reusable HA-ANT-Plus runtime/protocol core into HA-Fitness."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

CORE_FILES = (
    "adapter.py",
    "receiver.py",
    "remote.py",
    "decoder.py",
    "decoder_adapters.py",
    "openant_bridge.py",
    "const.py",
    "models.py",
    "capabilities.py",
    "diagnostics.py",
    "usb_selected.py",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default=str(Path.home() / "HA-ANT-Plus" / "custom_components" / "antplus"),
    )
    parser.add_argument("--fitness-root", default=".")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    root = Path(args.fitness_root).expanduser().resolve()
    destination = root / "custom_components" / "fitness" / "live" / "antplus_core"

    missing = [name for name in CORE_FILES if not (source / name).is_file()]
    if missing:
        raise SystemExit(f"HA-ANT-Plus runtime files missing: {', '.join(missing)}")

    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for name in CORE_FILES:
        shutil.copy2(source / name, destination / name)

    (destination / "__init__.py").write_text(
        '"""Vendored HA-ANT-Plus protocol/runtime core for Fitness."""\n'
    )
    const_path = destination / "const.py"
    text = const_path.read_text().replace('DOMAIN = "antplus"', 'DOMAIN = "fitness"', 1)
    const_path.write_text(text)

    version = str(manifest.get("version") or "unknown")
    (destination / "VENDORED_FROM_HA_ANT_PLUS.txt").write_text(version + "\n")

    fitness_manifest_path = root / "custom_components" / "fitness" / "manifest.json"
    if fitness_manifest_path.exists() and manifest.get("requirements"):
        fitness_manifest = json.loads(fitness_manifest_path.read_text())
        other = [
            req
            for req in fitness_manifest.get("requirements", [])
            if not str(req).lower().startswith("openant")
        ]
        fitness_manifest["requirements"] = other + list(manifest["requirements"])
        fitness_manifest_path.write_text(json.dumps(fitness_manifest, indent=2) + "\n")

    print(f"Vendored HA-ANT-Plus {version} runtime core from {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
