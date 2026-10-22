#!/usr/bin/env python3
"""Rebuild the Ollama alias and install this distribution; stdlib only."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:11434"
BASE = "qwen3.5:2b"
MODEL = "qwen3.5:2b-64k"
EXPECTED_PARAMS = {
    "num_ctx": 65536,
    "presence_penalty": 1.5,
    "temperature": 1,
    "top_k": 20,
    "top_p": 0.95,
}


def api(path: str, data: dict | None = None) -> dict:
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        API + path, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def run(*args: str, env: dict | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(list(args), check=True, cwd=ROOT, env=env)


def find_model(models: list[dict], name: str) -> dict | None:
    return next((m for m in models if m.get("name") == name), None)


def parameter_values(text: str) -> dict[str, float]:
    result = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in EXPECTED_PARAMS:
            result[parts[0]] = float(parts[1])
    return result


def model_errors(model: dict) -> list[str]:
    params = parameter_values(model.get("parameters", ""))
    errors = [
        f"{key}: expected {expected}, got {params.get(key)!r}"
        for key, expected in EXPECTED_PARAMS.items()
        if params.get(key) != expected
    ]
    if "tools" not in model.get("capabilities", []):
        errors.append("model does not advertise tool calling")
    if model.get("details", {}).get("family") != "qwen35":
        errors.append("model family is not qwen35")
    return errors


def weights_id(model: dict) -> str:
    # Ollama's generated Modelfile identifies the underlying weights, not the alias.
    match = re.search(r"(?m)^FROM\s+(.+)$", model.get("modelfile", ""))
    return match.group(1).strip() if match else ""


def ensure_models(allow_drift: bool = False, check_only: bool = False) -> None:
    lock = json.loads((ROOT / "setup-lock.json").read_text(encoding="utf-8"))
    try:
        models = api("/api/tags")["models"]
    except (OSError, ValueError, KeyError) as exc:
        raise RuntimeError(
            f"Ollama is not responding at {API}. Start the Ollama app or `ollama serve`."
        ) from exc
    # Do not let an inherited OLLAMA_HOST send the CLI to a different server.
    env = dict(os.environ, OLLAMA_HOST=API)
    base = find_model(models, BASE)
    if base is None:
        if check_only:
            raise RuntimeError(f"Missing base model: {BASE}")
        run("ollama", "pull", BASE, env=env)
        base = find_model(api("/api/tags")["models"], BASE)
    if base is None:
        raise RuntimeError(f"Ollama did not register {BASE} after pulling it")
    recorded = lock["ollama"]["base_model"]["digest"]
    if base.get("digest") != recorded:
        message = (
            f"{BASE} differs from the recorded source model.\n"
            f"Recorded: {recorded}\nInstalled: {base.get('digest')}"
        )
        if not allow_drift:
            raise RuntimeError(message + "\nReview the change; pass --allow-model-drift to accept it.")
        print("WARNING:", message)
    base_info = api("/api/show", {"model": BASE})
    existing = find_model(api("/api/tags")["models"], MODEL)
    if existing is None:
        if check_only:
            raise RuntimeError(f"Missing profile alias: {MODEL}")
        run("ollama", "create", MODEL, "-f", str(ROOT / "Modelfile"), env=env)
    actual = api("/api/show", {"model": MODEL})
    errors = model_errors(actual)
    if not weights_id(actual) or weights_id(actual) != weights_id(base_info):
        errors.append(f"weights differ from the installed {BASE} base")
    if errors:
        raise RuntimeError(
            f"{MODEL} does not match this setup; it was NOT overwritten.\n"
            + "\n".join(errors)
            + "\nRename/remove that alias deliberately before retrying."
        )
    print(f"Verified {MODEL}: matching base weights, tool calling, and all model parameters.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="tiny-web-code", help="New Hermes profile name")
    parser.add_argument("--skip-model", action="store_true", help="Install profile files only")
    parser.add_argument("--check-models", action="store_true", help="Validate existing models; no install or download")
    parser.add_argument("--allow-model-drift", action="store_true", help="Accept a changed upstream base-model digest")
    args = parser.parse_args()
    if args.skip_model and args.check_models:
        parser.error("--skip-model and --check-models cannot be combined")
    required = ("ollama",) if args.check_models else (("hermes", "git") if args.skip_model else ("hermes", "git", "ollama"))
    for command in required:
        if shutil.which(command) is None:
            parser.error(f"Required command not found: {command}. See README.md for prerequisites.")
    if not args.skip_model:
        ensure_models(args.allow_model_drift, args.check_models)
    if not args.check_models:
        # Native installer refuses an existing profile. Never force, switch defaults,
        # write credentials, or execute arbitrary post-install hooks.
        run("hermes", "profile", "install", str(ROOT), "--name", args.name, "--yes")
        print(f"Installed. Start with: hermes -p {args.name}")
        if args.skip_model:
            print("Model setup was skipped; inference requires the Ollama alias to exist.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError, urllib.error.URLError, ValueError) as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
