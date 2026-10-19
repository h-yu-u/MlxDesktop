"""Tavily Search/Extract. Response size is bounded and per-result failures are respected."""

import json
from typing import Any

import httpx

from mlx_studio_runtime.domain.errors import RuntimeErrorInfo, RuntimeFault
from mlx_studio_runtime.domain.web import PageRead, SearchHit, WebConfig


class Tavily:
    async def _post(
        self, endpoint: str, config: WebConfig, credential: str, body: dict[str, object]
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=config.timeout_seconds, follow_redirects=False, trust_env=False
            ) as client:
                async with client.stream(
                    "POST",
                    f"{config.base_url}/{endpoint}",
                    json=body,
                    headers={"Authorization": f"Bearer {credential}"},
                ) as response:
                    response.raise_for_status()
                    buffer = bytearray()
                    async for chunk in response.aiter_bytes():
                        buffer.extend(chunk)
                        if len(buffer) > 2 * 1024 * 1024:
                            raise ValueError("WEB_RESPONSE_TOO_LARGE")
            data = json.loads(buffer)
            if not isinstance(data, dict):
                raise ValueError("WEB_RESPONSE_INVALID")
            return data
        except httpx.TimeoutException as error:
            raise RuntimeFault(
                RuntimeErrorInfo("WEB_SEARCH_TIMEOUT", "联网检索超时", True)
            ) from error
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeFault(
                RuntimeErrorInfo("WEB_SEARCH_FAILED", "搜索服务请求失败", True)
            ) from error

    async def search(self, query: str, config: WebConfig, credential: str) -> list[SearchHit]:
        data = await self._post(
            "search",
            config,
            credential,
            {
                "query": query,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
                "include_favicon": False,
                "max_results": config.max_results,
            },
        )
        hits: list[SearchHit] = []
        results = data.get("results", [])
        if not isinstance(results, list):
            raise RuntimeFault(RuntimeErrorInfo("WEB_SEARCH_FAILED", "搜索服务响应无效", True))
        for item in results[: config.max_results]:
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                hits.append(
                    SearchHit(
                        str(item.get("title", "网页"))[:300],
                        item["url"],
                        item["content"][:6000] if isinstance(item.get("content"), str) else "",
                        item.get("published_date")
                        if isinstance(item.get("published_date"), str)
                        else None,
                    )
                )
        return hits

    async def read(self, urls: list[str], config: WebConfig, credential: str) -> list[PageRead]:
        data = await self._post("extract", config, credential, {"urls": urls, "format": "text"})
        results = data.get("results", [])
        if not isinstance(results, list):
            raise RuntimeFault(RuntimeErrorInfo("WEB_SEARCH_FAILED", "正文服务响应无效", True))
        return [
            PageRead(item["url"], item["raw_content"][:12000])
            for item in results
            if isinstance(item, dict)
            and item.get("url") in urls
            and isinstance(item.get("raw_content"), str)
            and item["raw_content"].strip()
        ]
