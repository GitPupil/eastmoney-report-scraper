"""Eastmoney HTTP client and list-fetching helpers."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import parse as urlparse
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from .constants import LIST_API, USER_AGENT
from .utils import log_event


def http_get(url: str, timeout: int = 20) -> str:
    req = urlrequest.Request(url, headers={"User-Agent": USER_AGENT})
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_get_with_retry(
    url: str,
    timeout: int,
    retries: int,
    retry_delay: float,
    log_path: Path,
    label: str,
) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 2):
        try:
            return http_get(url, timeout=timeout)
        except (URLError, HTTPError, TimeoutError, ValueError) as exc:
            last_error = exc
            log_event(log_path, "warn", f"{label} failed", attempt=attempt, url=url, error=repr(exc))
            if attempt <= retries:
                time.sleep(retry_delay)
    raise RuntimeError(f"{label} failed after retries: {last_error!r}")


def build_list_url(target_date: str, page_no: int, page_size: int, qtype: int) -> str:
    params = {
        "industryCode": "*",
        "pageSize": str(page_size),
        "industry": "*",
        "rating": "*",
        "ratingChange": "*",
        "beginTime": target_date,
        "endTime": target_date,
        "pageNo": str(page_no),
        "fields": "",
        "qType": str(qtype),
        "orgCode": "",
        "rcode": "",
    }
    return f"{LIST_API}?{urlparse.urlencode(params)}"


def fetch_report_list(
    target_date: str,
    page_size: int,
    qtype: int,
    timeout: int,
    retries: int,
    retry_delay: float,
    log_path: Path,
) -> List[Dict[str, Any]]:
    first = json.loads(
        http_get_with_retry(
            build_list_url(target_date, 1, page_size, qtype),
            timeout,
            retries,
            retry_delay,
            log_path,
            "list_page_1",
        )
    )
    hits = int(first.get("hits") or 0)
    data = list(first.get("data") or [])
    total_pages = max(1, math.ceil(hits / page_size))
    for page_no in range(2, total_pages + 1):
        page = json.loads(
            http_get_with_retry(
                build_list_url(target_date, page_no, page_size, qtype),
                timeout,
                retries,
                retry_delay,
                log_path,
                f"list_page_{page_no}",
            )
        )
        data.extend(page.get("data") or [])
    return data

