from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import requests

from market_radar.ai_provider import call_model_review


class AIProviderFallbackTests(unittest.TestCase):
    def test_clario_transport_timeout_uses_alternate_endpoint(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"verdict":"WATCH","confidence":0.8,'
                            '"reasons":[],"risk_flags":[]}'
                        )
                    }
                }
            ]
        }
        response.raise_for_status.return_value = None

        with patch(
            "market_radar.ai_provider._provider_config",
            return_value=(
                "test-key",
                "ClarioHub",
                ["https://primary.test/v1", "https://fallback.test/v1"],
            ),
        ), patch(
            "market_radar.ai_provider._rate_limited_post",
            side_effect=[requests.Timeout("primary timeout"), response],
        ) as post:
            result = call_model_review(
                {"symbol": "TESTUSDT"},
                system_prompt="test",
                model="gemini-3.7-flash",
                provider="clario",
            )

        self.assertEqual(result["verdict"], "WATCH")
        self.assertEqual(result["model"], "gemini-3.7-flash")
        self.assertEqual(post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
