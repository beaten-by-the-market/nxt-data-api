from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Optional, Union

import pandas as pd
import requests

from . import endpoints, transport
from .exceptions import NXTFetchError

DateLike = Union[str, date, datetime]

# 폭주 방지용 상한. 한 화면이 이보다 많은 페이지를 낼 일은 없다.
MAX_PAGES = 200

# 넥스트레이드 서버 시각대. DST가 없어 고정 오프셋으로 충분하다
# (tz 데이터베이스 설치 여부와 무관하게 동작한다).
KST = timezone(timedelta(hours=9))


def _drop_paging_fields(df: pd.DataFrame, **_: Any) -> pd.DataFrame:
    """jqGrid가 모든 행에 끼워 보내는 페이징/검색/감사 필드를 제거합니다."""
    present = [c for c in endpoints.PAGING_FIELDS if c in df.columns]
    return df.drop(columns=present) if present else df


def _coerce_types(df: pd.DataFrame, **_: Any) -> pd.DataFrame:
    """가격·수량 필드를 숫자로 바꾸고 문자열 필드의 공백을 정리합니다.

    날짜/시각/코드 필드(aggDd, nowDd, creTime, isuSrdCd ...)는 앞자리 0이
    의미를 가지므로 문자열로 남깁니다. epoch ms 필드(registDt)만 KST datetime이
    됩니다.
    """
    if df.empty:
        return df
    for col in endpoints.NUMERIC_FIELDS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in endpoints.EPOCH_MS_FIELDS:
        if col in df.columns:
            df[col] = pd.to_datetime(
                pd.to_numeric(df[col], errors="coerce"), unit="ms", utc=True
            ).dt.tz_convert(KST)
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(lambda v: v.strip() if isinstance(v, str) else v)
    return df


def _rename_korean(df: pd.DataFrame, **_: Any) -> pd.DataFrame:
    """뜻이 분명한 필드에 한글 컬럼명을 붙입니다 (매핑에 없으면 원래 이름 유지)."""
    return df.rename(columns=endpoints.COLUMN_LABELS)


def _drop_unused(df: pd.DataFrame, **_: Any) -> pd.DataFrame:
    """넥스트레이드가 항상 null/0으로 채워 보내는 미사용 필드를 제거합니다."""
    present = [c for c in endpoints.UNUSED_FIELDS if c in df.columns]
    return df.drop(columns=present) if present else df


_POST_PROCESSORS: dict[str, Callable[..., Any]] = {
    "drop_paging_fields": _drop_paging_fields,
    "coerce_types": _coerce_types,
    "rename_korean": _rename_korean,
    "drop_unused": _drop_unused,
}


def register_post_processor(name: str, func: Callable[..., Any]) -> None:
    """외부에서 커스텀 후처리를 추가하고 싶을 때."""
    _POST_PROCESSORS[name] = func


def _as_yyyymmdd(value: DateLike) -> str:
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y%m%d")
    text = str(value).replace("-", "").replace("/", "").strip()
    if len(text) != 8 or not text.isdigit():
        raise NXTFetchError(f"Invalid date: {value!r}. Use 'YYYYMMDD' or a date object.")
    return text


def _normalize_request_params(params: dict[str, Any]) -> dict[str, Any]:
    """사용자 친화 옵션(date/market/keyword)을 넥스트레이드 원시 파라미터로 바꿉니다."""
    normalized = dict(params)

    day = normalized.pop("date", None)
    if day is not None:
        normalized["scAggDd"] = _as_yyyymmdd(day)
    elif isinstance(normalized.get("scAggDd"), (datetime, date)):
        normalized["scAggDd"] = _as_yyyymmdd(normalized["scAggDd"])

    market = normalized.pop("market", None)
    if market is not None:
        key = str(market).upper()
        if key not in endpoints.MARKETS:
            raise NXTFetchError(
                f"Unknown market: {market!r}. "
                f"Use one of {sorted(set(endpoints.MARKETS))}."
            )
        normalized["scMktId"] = endpoints.MARKETS[key]

    keyword = normalized.pop("keyword", None)
    if keyword is not None:
        normalized["searchKeyword"] = keyword

    # None은 "이 파라미터를 보내지 않음"으로 처리합니다.
    return {k: v for k, v in normalized.items() if v is not None}


def fetch(
    name: str,
    *,
    session: Optional[requests.Session] = None,
    post: Optional[list[str]] = None,
    paginate: bool = True,
    **params: Any,
) -> pd.DataFrame:
    """카탈로그에 등록된 넥스트레이드 화면을 호출해 DataFrame으로 반환합니다.

    Parameters
    ----------
    name : 카탈로그 이름 (endpoints.ENDPOINTS의 키)
    session : 재사용할 requests.Session. None이면 매 호출마다 새 세션.
    post : 카탈로그의 post를 override하고 싶을 때 (보통 불필요)
    paginate : True면 응답의 `records`에 도달할 때까지 pageIndex를 올려가며 이어 받음.
        기본 pageUnit(10000)이면 대개 한 번에 다 받으므로 추가 호출이 없습니다.
        False면 요청한 pageIndex까지의 누적분만 받습니다(아래 주의 참고).
    **params : 화면에 전달할 추가/오버라이드 파라미터 (defaults에 머지됨).
        값이 None이면 해당 파라미터를 전송하지 않습니다.
        친절한 별칭도 받습니다:
            date="20260812" / date(2026, 8, 12)  → scAggDd (생략 시 당일 실시간)
            market="KOSPI" | "KOSDAQ" | "ALL"    → scMktId
            keyword="005930" | "삼성"            → searchKeyword

    Returns
    -------
    DataFrame. `df.attrs`에 응답 봉투 정보가 담깁니다:
        endpoint, screen, records(전체 건수), set_time(집계 시각), pages(받은 페이지 수)
    """
    spec = endpoints.get(name)
    list_key = spec["list_key"]
    merged = _normalize_request_params({**spec.get("defaults", {}), **params})

    rows: list[dict] = []
    payload: dict[str, Any] = {}
    page = int(merged.get("pageIndex", 1) or 1)
    pages_read = 0

    while True:
        payload = transport.grid_post(
            spec["path"],
            {**merged, "pageIndex": page},
            session=session,
            referer=spec["referer"],
        )
        chunk = payload.get(list_key)
        if chunk is None:
            raise NXTFetchError(
                f"Endpoint {name!r} response has no {list_key!r} key. "
                f"Got: {sorted(payload)}"
            )
        pages_read += 1

        # 넥스트레이드의 pageIndex는 "그 페이지만"이 아니라 "1~N페이지 누적"을
        # 돌려준다(무한스크롤 방식). 그래서 이어 붙이지 않고 교체한다.
        grew = len(chunk) > len(rows)
        rows = chunk

        records = payload.get("records") or payload.get("totalCnt") or 0
        if not paginate or not grew or len(rows) >= records:
            break
        page += 1
        if pages_read >= MAX_PAGES:
            raise NXTFetchError(
                f"Endpoint {name!r} exceeded {MAX_PAGES} pages "
                f"({len(rows)}/{records} rows). Raise pageUnit or narrow the query."
            )

    df = pd.DataFrame(rows)
    for proc_name in post if post is not None else spec.get("post", []):
        if proc_name not in _POST_PROCESSORS:
            raise NXTFetchError(f"Unknown post processor: {proc_name!r}")
        df = _POST_PROCESSORS[proc_name](df)

    df.attrs.update(
        endpoint=name,
        screen=spec.get("screen"),
        records=payload.get("records"),
        set_time=payload.get("setTime"),
        pages=pages_read,
    )
    return df


def _business_days(start: DateLike, end: DateLike) -> list[str]:
    d = datetime.strptime(_as_yyyymmdd(start), "%Y%m%d")
    last = datetime.strptime(_as_yyyymmdd(end), "%Y%m%d")
    if d > last:
        raise NXTFetchError(f"start ({start!r}) is after end ({end!r}).")
    days = []
    while d <= last:
        if d.weekday() < 5:  # 주말은 애초에 0건이라 건너뜁니다.
            days.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return days


def fetch_range(
    name: str,
    start: DateLike,
    end: DateLike,
    *,
    session: Optional[requests.Session] = None,
    pause: float = 0.2,
    dates: Optional[Iterable[DateLike]] = None,
    **params: Any,
) -> pd.DataFrame:
    """기간 조회. 넥스트레이드는 하루씩만 조회되므로 영업일을 돌며 이어 붙입니다.

    휴장일은 0건으로 오므로 결과에서 자연히 빠집니다. 조회한 날짜 목록과
    데이터가 없던 날짜는 `df.attrs["dates"]` / `df.attrs["empty_dates"]`에 담깁니다.

    `dates=`로 영업일 목록을 직접 주면 start/end 대신 그 목록만 조회합니다.
    (실제 휴장일 달력을 쓰면 불필요한 호출을 줄일 수 있습니다.)
    """
    day_list = (
        [_as_yyyymmdd(d) for d in dates]
        if dates is not None
        else _business_days(start, end)
    )
    s = session or requests.Session()

    frames: list[pd.DataFrame] = []
    empty: list[str] = []
    for i, day in enumerate(day_list):
        df = fetch(name, session=s, date=day, **params)
        if df.empty:
            empty.append(day)
        else:
            frames.append(df)
        if pause and i < len(day_list) - 1:
            time.sleep(pause)

    combined = (
        pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    )
    # concat이 첫 날짜의 attrs(records/set_time/pages)를 물려받을 수 있는데,
    # 기간 결과에는 맞지 않는 값이라 지우고 새로 채웁니다.
    combined.attrs.clear()
    combined.attrs.update(
        endpoint=name,
        screen=endpoints.get(name).get("screen"),
        dates=day_list,
        empty_dates=empty,
    )
    return combined


def list_endpoints() -> list[str]:
    return sorted(endpoints.ENDPOINTS)


def endpoint_info(name: str) -> dict:
    return dict(endpoints.get(name))
