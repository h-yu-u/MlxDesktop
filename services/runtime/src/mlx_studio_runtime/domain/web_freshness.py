"""Pure calendar windows and evidence date checks for time-sensitive questions."""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

from mlx_studio_runtime.domain.web import SearchHit

DATED = re.compile(r"(?<!\d)(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})(?:日)?(?!\d)")


@dataclass(frozen=True)
class SearchFreshness:
    start: date
    end: date
    time_range: str

    @property
    def label(self) -> str:
        if self.start == self.end:
            return self.end.isoformat()
        return f"{self.start.isoformat()} 至 {self.end.isoformat()}"


def freshness_window(query: str, now: datetime) -> SearchFreshness | None:
    # Explicit historical dates take precedence over words in an article's title.
    if DATED.search(query):
        return None
    text = query.replace("今日头条", "")
    if re.search(r"今天|今日|本日|\btoday\b", text, re.I):
        days, time_range = 1, "day"
    elif re.search(r"最新|近期|最近|当前|\b(latest|current|recent)\b", text, re.I):
        days, time_range = 7, "week"
    else:
        return None
    return SearchFreshness(now.date() - timedelta(days=days - 1), now.date(), time_range)


def search_query(query: str, window: SearchFreshness | None) -> str:
    return f"{query}（资料日期：{window.label}）" if window else query


def publication_date(value: str | None, now: datetime) -> date | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    return parsed.astimezone(now.tzinfo).date() if parsed.tzinfo else parsed.date()


def fresh_hit(hit: SearchHit, window: SearchFreshness | None, now: datetime) -> bool:
    if window is None:
        return True
    explicit: list[date] = []
    for match in DATED.finditer(f"{hit.title} {hit.url}"):
        try:
            explicit.append(date(*(int(part) for part in match.groups())))
        except ValueError:
            return False
    # Reject old dated articles even when a provider reports a recent crawl/update.
    if any(value < window.start or value > window.end for value in explicit):
        return False
    published = publication_date(hit.published_at, now)
    return window.start <= published <= window.end if published else bool(explicit)
