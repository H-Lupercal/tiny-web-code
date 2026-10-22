"""Offline tests; mock Ollama only at the HTTP/subprocess boundary."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("profile_setup", ROOT / "scripts/setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def test_parameters(self):
        values = setup.parameter_values("num_ctx 65536\ntemperature 1\nnoise value\n")
        self.assertEqual(values, {"num_ctx": 65536.0, "temperature": 1.0})

    def valid_info(self):
        return {
            "parameters": "\n".join(f"{k} {v}" for k, v in setup.EXPECTED_PARAMS.items()),
            "capabilities": ["completion", "tools"],
            "details": {"family": "qwen35"},
            "modelfile": "FROM /models/sha256-test-weights\n",
        }

    def fixture(self, drift=False, alias=True, bad_weights=False):
        recorded = json.loads((ROOT / "setup-lock.json").read_text())["ollama"]["base_model"]["digest"]
        models = [{"name": setup.BASE, "digest": "changed" if drift else recorded}]
        if alias:
            models.append({"name": setup.MODEL, "digest": "test-alias"})

        def api(path, data=None):
            if path == "/api/tags":
                return {"models": models}
            self.assertEqual(path, "/api/show")
            info = self.valid_info()
            if bad_weights and data["model"] == setup.MODEL:
                info["modelfile"] = "FROM /models/sha256-different\n"
            return info
        return api

    def test_valid_model_parameters(self):
        self.assertEqual(setup.model_errors(self.valid_info()), [])

    def test_missing_context_rejected(self):
        info = self.valid_info()
        info["parameters"] = "temperature 1"
        self.assertTrue(any("num_ctx" in x for x in setup.model_errors(info)))

    def test_existing_matching_model_not_overwritten(self):
        with patch.object(setup, "api", side_effect=self.fixture()), patch.object(setup, "run") as run:
            setup.ensure_models()
            run.assert_not_called()

    def test_changed_base_requires_explicit_consent(self):
        with patch.object(setup, "api", side_effect=self.fixture(drift=True)), patch.object(setup, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "differs from the recorded"):
                setup.ensure_models()
            run.assert_not_called()

    def test_changed_base_opt_in(self):
        with patch.object(setup, "api", side_effect=self.fixture(drift=True)), patch.object(setup, "run") as run:
            setup.ensure_models(allow_drift=True)
            run.assert_not_called()

    def test_existing_wrong_weights_not_overwritten(self):
        with patch.object(setup, "api", side_effect=self.fixture(bad_weights=True)), patch.object(setup, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "weights differ"):
                setup.ensure_models()
            run.assert_not_called()

    def test_missing_alias_created_from_modelfile(self):
        with patch.object(setup, "api", side_effect=self.fixture(alias=False)), patch.object(setup, "run") as run:
            setup.ensure_models()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[:4], ("ollama", "create", setup.MODEL, "-f"))
            self.assertEqual(run.call_args.kwargs["env"]["OLLAMA_HOST"], setup.API)

    def test_check_only_never_creates_alias(self):
        with patch.object(setup, "api", side_effect=self.fixture(alias=False)), patch.object(setup, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "Missing profile alias"):
                setup.ensure_models(check_only=True)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
