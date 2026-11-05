#!/usr/bin/env python3
"""Offline consistency and scope checks; NOT a ReShade shader compiler."""
import configparser
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def validate(root=ROOT):
    errors = []
    required = ["AGENTS.md", ".agents/skills/nfsuc-visual-modding/SKILL.md", "LICENSE", "README.md",
                "VERSION", "THIRD_PARTY.md", "docs/STATUS.md", "docs/LOCAL_TESTING.md",
                "docs/FUSIONFIX.md", "docs/TOOLS.md", "docs/ASSET_PIPELINE.md", "docs/SHADER.md",
                "docs/RENDERING.md", "docs/ROADMAP.md", "tools/remaster.py", "tools/remaster.ps1"]
    for name in required:
        if not (root / name).is_file():
            errors.append(f"Missing {name}")
    source = (root / "shaders/NFSUCFoundation.fx").read_text(encoding="utf-8")
    techniques = set(re.findall(r"\btechnique\s+(\w+)", source))
    uniforms = set(re.findall(r"\buniform\s+float\s+(\w+)", source))
    for name in ("Hybrid", "Clean", "Cinematic"):
        path = root / "profiles" / (name + ".ini")
        text = path.read_text(encoding="utf-8")
        ini = configparser.ConfigParser()
        ini.optionxform = str
        ini.read_string("[ROOT]\n" + text)
        for key in ("Techniques", "TechniqueSorting"):
            for effect in ini["ROOT"][key].split(","):
                technique, sep, shader = effect.partition("@")
                if not sep or shader != "NFSUCFoundation.fx" or technique not in techniques:
                    errors.append(f"{path.name}: unavailable technique {effect}")
        if set(ini["NFSUCFoundation.fx"]) != uniforms:
            errors.append(f"{path.name}: uniforms differ from shader")
    policy = json.loads((root / "configs/fusionfix-visual-policy.json").read_text(encoding="utf-8"))
    if policy["default_enabled"] or any(s["enabled"] for s in policy["studies"].values()):
        errors.append("FusionFix experiments must remain off by default")
    prohibited = ("simrate", "fpslimit", "handling", "physics", "ai", "economy", "progression")
    approved = {"GRAPHICS.ShadowResolution", "GRAPHICS.CSMScaleFar", "GRAPHICS.ImproveSceneryLOD"}
    for study in policy["studies"].values():
        for key in study["changes"]:
            if key not in approved or any(p in key.lower() for p in prohibited):
                errors.append(f"Unapproved visual study setting: {key}")
    from tools.remaster import PAYLOAD
    expected = {"nfsuc-remaster/Shaders/NFSUCFoundation.fx": "shaders/NFSUCFoundation.fx",
                **{f"nfsuc-remaster/Profiles/{name}.ini": f"profiles/{name}.ini"
                   for name in ("Hybrid", "Clean", "Cinematic")}}
    if PAYLOAD != expected:
        errors.append("Installer allowlist differs from reviewed payload")
    for path in root.rglob("*"):
        if any(p in (".git", "local", "artifacts", "build", "__pycache__") for p in path.parts):
            continue
        if path.suffix.lower() in (".dll", ".exe", ".asi", ".dds", ".bun", ".bin", ".tpk"):
            errors.append(f"Unapproved distributable binary/game asset: {path.relative_to(root)}")
    return errors


def main():
    # Direct script invocation needs repository root for the tools namespace.
    sys.path.insert(0, str(ROOT))
    errors = validate()
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print("Configuration/scope checks PASS. Shader GPU compilation and game compatibility NOT tested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
