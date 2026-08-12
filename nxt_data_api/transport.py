from __future__ import annotations

from typing import Any, Optional

import requests

from .exceptions import NXTFetchError

BASE = "https://nextrade.co.kr"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)

DEFAULT_REFERER = "/menu/transactionStatusMain/menuList.do"


def _headers(referer: str) -> dict:
    return {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": BASE,
        "Referer": f"{BASE}{referer}",
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
    }


def grid_post(
    path: str,
    params: dict,
    *,
    session: Optional[requests.Session] = None,
    referer: str = DEFAULT_REFERER,
    timeout: int = 30,
) -> dict[str, Any]:
    """넥스트레이드 jqGrid 백엔드(`*List.do`)를 POST 호출해 JSON dict를 반환합니다.

    로그인/OTP가 필요 없습니다. 세션 쿠키(JSESSIONID)도 필수가 아니어서
    세션 없이 곧바로 POST해도 정상 응답합니다.
    """
    s = session or requests.Session()
    url = f"{BASE}/{path.lstrip('/')}"
    resp = s.post(url, data=params, headers=_headers(referer), timeout=timeout)
    if not resp.ok:
        raise NXTFetchError(
            f"NXT request failed: path={path} status={resp.status_code} "
            f"body_preview={resp.text[:120]!r}"
        )
    # 서버가 Content-Type을 text/html로 주지만 본문은 JSON입니다.
    resp.encoding = "UTF-8"
    try:
        payload = resp.json()
    except ValueError as e:
        raise NXTFetchError(
            f"JSON parse failed for path={path}: {e} body_preview={resp.text[:120]!r}"
        ) from e
    if not isinstance(payload, dict):
        raise NXTFetchError(
            f"Unexpected JSON shape for path={path}: {type(payload).__name__}"
        )
    return payload
