"""Temporal search must not present retrieval timestamps as publication evidence."""

import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from mlx_studio_runtime.adapters.web.tavily import Tavily
from mlx_studio_runtime.application.web_retrieval import WebRetrieval
from mlx_studio_runtime.domain.chat_context import build_context
from mlx_studio_runtime.domain.errors import RuntimeFault
from mlx_studio_runtime.domain.web import SearchHit, WebConfig
from mlx_studio_runtime.domain.web_freshness import (
    fresh_hit,
    freshness_window,
    search_query,
)

NOW = datetime.fromisoformat("2026-10-23T23:18:00+08:00")


class FreshnessTests(unittest.TestCase):
    def test_today_uses_user_calendar_and_does_not_rewrite_historical_questions(self):
        window = freshness_window("GitHub 今日热点", NOW)
        self.assertIsNotNone(window)
        self.assertEqual(window.label, "2026-10-23")
        self.assertIn("2026-10-23", search_query("今日热点", window))
        for query in [
            "MLX Apple Silicon",
            "今日头条的公司简介",
            "2025/07/27 GitHub 今日热门项目",
        ]:
            self.assertIsNone(freshness_window(query, NOW))
        self.assertEqual(
            freshness_window("最新热点", NOW).label, "2026-10-17 至 2026-10-23"
        )

    def test_rejects_old_unknown_future_and_misleading_updated_articles(self):
        window = freshness_window("今日热点", NOW)
        for hit in [
            SearchHit("Old", "https://example.com/a", "summary", "2025-07-27"),
            SearchHit("Unknown", "https://example.com/b", "summary"),
            SearchHit("Future", "https://example.com/c", "summary", "2026-10-24"),
            SearchHit(
                "【2025/07/27】GitHub 今日热门项目",
                "https://example.com/d",
                "old",
                "2026-10-23",
            ),
            SearchHit(
                "Old permalink",
                "https://example.com/2025/07/27/article",
                "old",
                "2026-10-23",
            ),
        ]:
            self.assertFalse(fresh_hit(hit, window, NOW), hit.title)
        self.assertTrue(
            fresh_hit(
                SearchHit("Today", "https://example.com", "current", "2026-10-23"),
                window,
                NOW,
            )
        )
        self.assertTrue(
            fresh_hit(
                SearchHit("2026年10月23日热点", "https://example.com", "current"),
                window,
                NOW,
            )
        )
        # UTC yesterday can be today in the user's timezone, and vice versa.
        self.assertTrue(
            fresh_hit(
                SearchHit(
                    "Today", "https://example.com", "current", "2026-10-22T18:00:00Z"
                ),
                window,
                NOW,
            )
        )
        self.assertFalse(
            fresh_hit(
                SearchHit(
                    "Yesterday", "https://example.com", "old", "2026-10-22T15:59:00Z"
                ),
                window,
                NOW,
            )
        )

    def test_prompt_carries_clock_and_distinct_source_dates(self):
        snapshot = build_context(
            "今日热点",
            [],
            [],
            [
                {
                    "id": "w1",
                    "kind": "web",
                    "title": "Report",
                    "url": "https://example.com",
                    "publishedAt": "2026-10-23",
                    "retrievedAt": NOW.isoformat(),
                    "representation": "snippet_only",
                    "text": "Verified summary",
                }
            ],
            8192,
            128,
            0,
            current_time=NOW.isoformat(),
        )
        self.assertIn(NOW.isoformat(), snapshot["messages"][0]["content"])
        self.assertIn("检索时间不是发布时间", snapshot["messages"][0]["content"])
        self.assertIn("发布时间: 2026-10-23", snapshot["prompt"])
        self.assertIn("检索时间: 2026-10-23T23:18:00+08:00", snapshot["prompt"])


class TemporalRetrievalTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_request_constrains_time_and_requests_publication_dates(
        self,
    ):
        adapter = Tavily()
        adapter._post = AsyncMock(return_value={"results": []})
        config = WebConfig("id", 1, "tavily", "https://api.tavily.com", "ref")
        with patch("mlx_studio_runtime.adapters.web.tavily.datetime") as clock:
            clock.now.return_value = NOW
            await adapter.search("GitHub 今日热点", config, "test")
        body = adapter._post.call_args.args[3]
        self.assertEqual(body["time_range"], "day")
        self.assertTrue(body["filter_by_published_date"])
        self.assertTrue(body["include_published_date"])
        self.assertIn("2026-10-23", body["query"])
        await adapter.search("MLX architecture", config, "test")
        self.assertNotIn("time_range", adapter._post.call_args.args[3])

    async def test_compatible_provider_cannot_bypass_local_date_validation(self):
        search = AsyncMock()
        search.search.return_value = [
            SearchHit("2025/07/27 GitHub", "https://example.com", "old", "2025-07-27")
        ]
        reader, secrets, policy = AsyncMock(), unittest.mock.Mock(), AsyncMock()
        secrets.resolve.return_value = "test"
        policy.allowed.return_value = True
        reader.read.return_value = []
        retrieval = WebRetrieval(search, reader, secrets, policy)
        config = WebConfig("id", 1, "tavily", "https://api.tavily.com", "ref")
        with patch("mlx_studio_runtime.application.web_retrieval.datetime") as clock:
            clock.now.return_value = NOW
            with self.assertRaises(RuntimeFault) as error:
                await retrieval.retrieve("今日热点", config, AsyncMock())
            self.assertEqual(error.exception.info.code, "WEB_FRESHNESS_UNVERIFIED")
            self.assertIn("2026-10-23", error.exception.info.message)
            reader.read.assert_not_awaited()
            search.search.return_value += [
                SearchHit(
                    "Current report", "https://example.com/new", "current", "2026-10-23"
                )
            ]
            result = await retrieval.retrieve("今日热点", config, AsyncMock())
        self.assertEqual(
            [item["title"] for item in result["sources"]], ["Current report"]
        )
        self.assertTrue(result["partial"])
