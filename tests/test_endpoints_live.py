"""Live tests that call 넥스트레이드.

Run: pytest tests/test_endpoints_live.py
Skip: set NXT_SKIP_LIVE=1.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pandas as pd
import pytest

from nxt_data_api import fetch, fetch_range

pytestmark = pytest.mark.skipif(
    os.getenv("NXT_SKIP_LIVE") == "1", reason="NXT_SKIP_LIVE set"
)

# 넥스트레이드 개장일. 이 날은 시범 10개 종목만 거래됐다 (삼성전자는 미포함).
LAUNCH_DAY = "20250304"
LAUNCH_DAY_ISSUE = "122870"  # 와이지엔터테인먼트 — 개장일 10종목 중 하나


def _recent_trading_day() -> str:
    """직전 평일. 휴장일이면 0건이 올 수 있으므로 건수 단언에는 쓰지 않는다."""
    d = datetime.today() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def test_regular_market_launch_day():
    df = fetch("regular_market", date=LAUNCH_DAY)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 10
    for col in ("isuSrdCd", "isuAbwdNm", "mktNm", "curPrc", "oppr", "hgpr", "lwpr",
                "accTdQty", "accTrval", "cptrTrdPmsnCdNm", "trdIpsbRsn"):
        assert col in df.columns
    assert df["aggDd"].unique().tolist() == [LAUNCH_DAY]
    assert df.attrs["records"] == 10
    assert df.attrs["set_time"].startswith("2025-03-04")


def test_closing_price_launch_day():
    df = fetch("closing_price", date=LAUNCH_DAY)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 10
    for col in ("isuSrdCd", "isuAbwdNm", "mktNm", "cspr", "accTdQty", "accTrval"):
        assert col in df.columns
    # 종가매매 화면은 정규시장의 시가/고가/저가·거래가능시장을 주지 않는다.
    assert "curPrc" not in df.columns
    assert "oppr" not in df.columns


def test_numeric_columns_are_numeric():
    df = fetch("regular_market", date=LAUNCH_DAY)
    assert pd.api.types.is_numeric_dtype(df["curPrc"])
    assert pd.api.types.is_numeric_dtype(df["accTrval"])
    assert pd.api.types.is_numeric_dtype(df["basePrc"])
    # 날짜/코드는 문자열로 남아야 한다 (앞자리 0 보존).
    assert df["aggDd"].dtype == object
    assert df["isuSrdCd"].iloc[0].startswith("A")


def test_market_filter_partitions_the_day():
    all_df = fetch("regular_market", date=LAUNCH_DAY)
    kospi = fetch("regular_market", date=LAUNCH_DAY, market="KOSPI")
    kosdaq = fetch("regular_market", date=LAUNCH_DAY, market="KOSDAQ")
    assert len(kospi) + len(kosdaq) == len(all_df)
    assert set(kospi["mktNm"]) <= {"KOSPI"}
    assert set(kosdaq["mktNm"]) <= {"KOSDAQ"}


def test_keyword_filter():
    df = fetch("regular_market", date=LAUNCH_DAY, keyword=LAUNCH_DAY_ISSUE)
    assert len(df) == 1
    assert df["isuSrdCd"].iloc[0] == f"A{LAUNCH_DAY_ISSUE}"


def test_pagination_matches_single_page():
    """작은 pageUnit으로 여러 번 받아도 한 번에 받은 것과 같아야 한다."""
    one_shot = fetch("regular_market", date=LAUNCH_DAY)
    paged = fetch("regular_market", date=LAUNCH_DAY, pageUnit=3)
    assert len(paged) == len(one_shot)
    assert paged.attrs["pages"] > 1
    assert sorted(paged["isuSrdCd"]) == sorted(one_shot["isuSrdCd"])


def test_pageindex_is_cumulative_not_sliced():
    """넥스트레이드의 pageIndex=N은 1~N페이지 누적분을 준다."""
    first = fetch("regular_market", date=LAUNCH_DAY, pageUnit=3, paginate=False)
    second = fetch(
        "regular_market", date=LAUNCH_DAY, pageUnit=3, pageIndex=2, paginate=False
    )
    assert len(first) == 3
    assert len(second) == 6
    assert second["isuSrdCd"].tolist()[:3] == first["isuSrdCd"].tolist()


def test_holiday_returns_empty():
    # 넥스트레이드 개장 전 (2025-03-04 개장).
    df = fetch("regular_market", date="20250228")
    assert df.empty
    assert df.attrs["records"] == 0


def test_snapshot_without_date():
    """날짜를 생략하면 당일 스냅샷. 개장 전이면 0건일 수 있다."""
    df = fetch("regular_market")
    assert isinstance(df, pd.DataFrame)
    assert df.attrs["set_time"]


def test_fetch_range_spans_days():
    df = fetch_range("regular_market", "20250304", "20250307", pause=0.2)
    assert isinstance(df, pd.DataFrame)
    assert df.attrs["dates"] == ["20250304", "20250305", "20250306", "20250307"]
    if not df.empty:
        assert set(df["aggDd"]) <= set(df.attrs["dates"])


def test_recent_day_is_reachable():
    df = fetch("closing_price", date=_recent_trading_day())
    assert isinstance(df, pd.DataFrame)
