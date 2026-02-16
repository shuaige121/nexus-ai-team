from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from nexus_v1.model_router import ModelRouter


class LiteLLMSmokeTest(unittest.TestCase):
    def test_ollama_admin_provider_dry_run(self) -> None:
        captured: dict[str, object] = {}

        def fake_completion(**kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {
                "model": kwargs["model"],
                "choices": [{"message": {"content": "pong"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            }

        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://localhost:11434"}, clear=False):
            router = ModelRouter(completion_fn=fake_completion)
            response = router.chat(
                [{"role": "user", "content": "ping"}],
                role="admin",
                max_tokens=32,
            )

        self.assertEqual("pong", response.content)
        self.assertEqual("ollama/qwen3:8b", captured["model"])
        self.assertEqual("http://localhost:11434", captured["api_base"])
        self.assertEqual(32, captured["max_tokens"])
        self.assertEqual(7, response.usage["total_tokens"] if response.usage else -1)


if __name__ == "__main__":
    unittest.main()

