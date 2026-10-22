#!/usr/bin/env python3
"""Verify an installed profile using Hermes' own dependency runtime."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import unittest


def run_checks(home: Path, web: bool) -> None:
    os.environ["HERMES_HOME"] = str(home)
    from hermes_cli.config import load_config_readonly
    config = load_config_readonly()
    assert config["model"]["default"] == "qwen3.5:2b-64k"
    assert config["model"]["provider"] == "custom"
    assert config["model"]["base_url"] == "http://127.0.0.1:11434/v1"
    assert config["model"]["context_length"] == 65536
    assert config["platform_toolsets"]["cli"] == ["web", "code_execution"]
    assert config["code_execution"]["mode"] == "strict"
    print("PASS: installed profile settings")

    from model_tools import get_tool_definitions
    schemas = get_tool_definitions(
        enabled_toolsets=config["platform_toolsets"]["cli"],
        disabled_toolsets=config["agent"].get("disabled_toolsets", []),
        quiet_mode=True,
        skip_tool_search_assembly=True,
    )
    names = {s["function"]["name"] for s in schemas}
    assert {"web_search", "web_extract", "execute_code"} <= names, names
    assert not {"terminal", "read_file", "write_file", "memory"} & names, names
    print("PASS: web search, extraction, and code-execution tools registered")

    from tools.code_execution_tool import execute_code
    result = json.loads(execute_code(
        "print(sum(i * i for i in range(10)))",
        task_id="tiny-web-code-smoke",
        enabled_tools=["web_search", "web_extract"],
        reset=True,
    ))
    assert result.get("exit_code") == 0, result
    assert result.get("output", "").strip() == "285", result
    print("PASS: Python code execution returned 285")
    if web:
        from tools.web_tools import web_search_tool
        search = json.loads(web_search_tool("Python programming official documentation", limit=2))
        hits = search.get("data", {}).get("web", [])
        assert hits and all(h.get("url") for h in hits), search
        print(f"PASS: live search returned {len(hits)} linked results")
        print(json.dumps([{"title": h.get("title"), "url": h["url"]} for h in hits]))


def load_tests(loader, tests, pattern):
    home = Path(os.environ["TINY_WEB_CODE_SMOKE_HOME"])
    web = os.environ.get("TINY_WEB_CODE_SMOKE_WEB") == "1"
    return unittest.TestSuite([unittest.FunctionTestCase(lambda: run_checks(home, web))])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True, type=Path, help="Installed profile directory")
    parser.add_argument("--web", action="store_true", help="Also perform a real network search")
    args = parser.parse_args()
    home = args.home.expanduser().resolve()
    if not (home / "distribution.yaml").is_file():
        parser.error("--home must identify an installed distribution profile")
    env = dict(os.environ, HERMES_HOME=str(home),
               TINY_WEB_CODE_SMOKE_HOME=str(home),
               TINY_WEB_CODE_SMOKE_WEB="1" if args.web else "0")
    # unittest discovery imports this file with the Hermes-managed interpreter
    # and its dependencies. Do not guess a venv or install into system Python.
    return subprocess.run([
        "hermes", "--run-module", "unittest", "discover", "-s",
        str(Path(__file__).resolve().parent), "-p", "smoke.py", "-v",
    ], env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
