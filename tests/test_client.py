"""Offline tests — 넥스트레이드를 호출하지 않고 요청 조립/후처리만 검증합니다."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from nxt_data_api import client, endpoint_info, fetch, fetch_range, list_endpoints
from nxt_data_api.exceptions import NXTFetchError, UnknownEndpointError


def _row(**extra) -> dict:
    """실제 응답 행 모양 — 페이징 필드가 데이터에 섞여 온다."""
    base = {
        "nowPage": 1,
        "pageUnit": 5,
        "rnum": 0,
        "searchKeyword": None,
        "scAggDd": None,
        "scMktId": None,
        "registUserId": "admin",
        "registDt": 1786532703598,
        "updateDt": None,
        "totalCnt": 0,
        "aggDd": "20260812",
        "mktId": "STK",
        "mktNm": "KOSPI",
        "isuCd": "KR7005930003",
        "isuSrdCd": "A005930",
        "isuAbwdNm": "삼성전자",
        "basePrc": "239500",
        "trdvapBegnDd": "        ",
        "accTdQty": 1058,
        "accTrval": 270319000,
    }
    base.update(extra)
    return base


@pytest.fixture
def capture(monkeypatch):
    """grid_post를 가로채 요청 파라미터를 기록하고 가짜 응답을 돌려줍니다."""
    calls: list[dict] = []
    pages: list[dict] = []

    def fake_grid_post(path, params, *, session=None, referer=None, timeout=30):
        calls.append({"path": path, "params": dict(params), "referer": referer})
        if pages:
            return pages[min(len(calls), len(pages)) - 1]
        return {
            "records": 1,
            "totalCnt": 1,
            "total": 1,
            "page": 1,
            "setTime": "2026-08-12 20:05",
            "brdinfoTimeList": [_row(curPrc=258000, creTime="200500")],
            "brdinfoEndList": [_row(cspr=255500)],
        }

    monkeypatch.setattr(client.transport, "grid_post", fake_grid_post)
    return calls, pages


def test_catalog_lists_registered_endpoints():
    assert list_endpoints() == ["closing_price", "regular_market"]
    assert endpoint_info("regular_market")["list_key"] == "brdinfoTimeList"
    assert endpoint_info("closing_price")["path"] == "brdinfoEnd/brdinfoEndList.do"


def test_unknown_endpoint_raises():
    with pytest.raises(UnknownEndpointError):
        fetch("nope")


def test_friendly_params_map_to_raw(capture):
    calls, _ = capture

    fetch("regular_market", date="2026-08-12", market="KOSDAQ", keyword="005930")
    fetch("closing_price", date=date(2026, 8, 12), market="ALL")

    assert calls[0]["path"] == "brdinfoTime/brdinfoTimeList.do"
    assert calls[0]["referer"] == "/menu/transactionStatusMain/menuList.do"
    assert calls[0]["params"]["scAggDd"] == "20260812"
    assert calls[0]["params"]["scMktId"] == "KSQ"
    assert calls[0]["params"]["searchKeyword"] == "005930"
    assert calls[0]["params"]["pageIndex"] == 1

    assert calls[1]["path"] == "brdinfoEnd/brdinfoEndList.do"
    assert calls[1]["params"]["scAggDd"] == "20260812"
    assert calls[1]["params"]["scMktId"] == ""


def test_none_param_is_not_sent(capture):
    calls, _ = capture
    fetch("regular_market", searchKeyword=None)
    assert "searchKeyword" not in calls[0]["params"]


def test_bad_date_and_market_raise(capture):
    with pytest.raises(NXTFetchError):
        fetch("regular_market", date="2026-8-12")
    with pytest.raises(NXTFetchError):
        fetch("regular_market", market="NASDAQ")


def test_post_processing_drops_paging_and_coerces(capture):
    df = fetch("regular_market", date="20260812")

    for junk in ("nowPage", "rnum", "scAggDd", "registUserId", "totalCnt"):
        assert junk not in df.columns
    assert df["basePrc"].iloc[0] == 239500          # "239500" → 숫자
    assert df["aggDd"].iloc[0] == "20260812"        # 날짜는 문자열 유지
    assert df["trdvapBegnDd"].iloc[0] == ""         # 공백 문자열은 strip
    assert df.attrs["records"] == 1
    assert df.attrs["set_time"] == "2026-08-12 20:05"
    assert df.attrs["pages"] == 1


def test_epoch_ms_becomes_kst_datetime(capture):
    df = fetch("regular_market", date="20260812")
    stamp = df["registDt"].iloc[0]
    assert stamp.tz_localize is not None
    assert stamp.utcoffset() == timedelta(hours=9)
    assert stamp.strftime("%Y-%m-%d %H:%M") == "2026-08-12 20:05"


def test_optional_post_processors(capture):
    df = fetch(
        "regular_market",
        date="20260812",
        post=["drop_paging_fields", "coerce_types", "drop_unused", "rename_korean"],
    )
    assert "종목명" in df.columns
    assert "현재가" in df.columns
    assert "trdvapBegnDd" not in df.columns


def test_pagination_replaces_cumulative_pages(capture):
    """pageIndex=N은 1~N페이지 누적분을 준다. 이어 붙이면 중복이 된다."""
    calls, pages = capture
    pages.extend(
        [
            {"records": 3, "total": 2, "page": 1,
             "brdinfoTimeList": [_row(isuSrdCd="A1"), _row(isuSrdCd="A2")]},
            {"records": 3, "total": 2, "page": 2,
             "brdinfoTimeList": [_row(isuSrdCd="A1"), _row(isuSrdCd="A2"),
                                 _row(isuSrdCd="A3")]},
        ]
    )

    df = fetch("regular_market", date="20260812", pageUnit=2)

    assert len(df) == 3
    assert df["isuSrdCd"].tolist() == ["A1", "A2", "A3"]
    assert [c["params"]["pageIndex"] for c in calls] == [1, 2]
    assert df.attrs["pages"] == 2


def test_pagination_stops_when_rows_stop_growing(capture):
    """records가 부풀려져 있어도 응답이 안 늘면 멈춘다 (무한루프 방지)."""
    calls, pages = capture
    pages.extend(
        [
            {"records": 99, "total": 9, "page": 1,
             "brdinfoTimeList": [_row(isuSrdCd="A1")]},
            {"records": 99, "total": 9, "page": 2,
             "brdinfoTimeList": [_row(isuSrdCd="A1")]},
        ]
    )

    df = fetch("regular_market", date="20260812", pageUnit=1)

    assert len(df) == 1
    assert len(calls) == 2


def test_paginate_false_stops_after_first_page(capture):
    calls, pages = capture
    pages.extend(
        [
            {"records": 3, "total": 2, "page": 1,
             "brdinfoTimeList": [_row(), _row()]},
            {"records": 3, "total": 2, "page": 2,
             "brdinfoTimeList": [_row(), _row(), _row()]},
        ]
    )

    df = fetch("regular_market", date="20260812", pageUnit=2, paginate=False)

    assert len(df) == 2
    assert len(calls) == 1


def test_missing_list_key_raises(capture):
    _, pages = capture
    pages.append({"records": 0, "total": 1, "page": 1})
    with pytest.raises(NXTFetchError):
        fetch("regular_market", date="20260812")


def test_fetch_range_skips_weekends_and_empty_days(monkeypatch, capture):
    calls, _ = capture
    seen: list[str] = []

    original = client.fetch

    def spy(name, **kwargs):
        seen.append(kwargs["date"])
        # 2026-08-11은 휴장으로 가정
        if kwargs["date"] == "20260811":
            return pd.DataFrame()
        return original(name, **kwargs)

    monkeypatch.setattr(client, "fetch", spy)

    df = client.fetch_range("regular_market", "20260807", "20260812", pause=0)

    # 08-08(토), 08-09(일)은 아예 호출하지 않는다.
    assert seen == ["20260807", "20260810", "20260811", "20260812"]
    assert df.attrs["empty_dates"] == ["20260811"]
    assert len(df) == 3
    # 하루치 attrs가 기간 결과에 그대로 남아 있으면 오해를 부른다.
    assert "records" not in df.attrs
    assert "set_time" not in df.attrs


def test_fetch_range_rejects_reversed_range():
    with pytest.raises(NXTFetchError):
        fetch_range("regular_market", "20260812", "20260801", pause=0)
