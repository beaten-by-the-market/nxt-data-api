"""넥스트레이드(nextrade.co.kr) 거래현황 화면(*List.do) → 친절한 이름 카탈로그.

각 엔드포인트는 dict로 정의된다:
    "path": POST 경로 (예: "brdinfoTime/brdinfoTimeList.do")
    "list_key": 응답 JSON에서 행 배열이 담긴 키 (예: "brdinfoTimeList")
    "referer": Referer 헤더에 넣을 화면 경로
    "defaults": 호출 시 기본 파라미터 (호출자가 같은 키를 주면 덮어씀)
    "post": 호출 후 적용할 후처리 함수 이름 리스트 (client._POST_PROCESSORS 참조)

응답 봉투는 jqGrid 규약을 따른다:
    {"records": 전체행수, "totalCnt": 전체행수, "total": 페이지수, "page": 현재페이지,
     "setTime": "2026-08-12 20:05",  # 정규시장만
     "<list_key>": [ ... ]}

`pageUnit`을 크게 주면 한 번에 전부 받을 수 있고, 그렇지 않으면 client.fetch()가
`records`에 도달할 때까지 pageIndex를 올려가며 자동으로 이어 받는다.

주의 — pageIndex는 누적이다. 넥스트레이드는 `pageIndex=N`에 "N번째 페이지"가
아니라 "1~N페이지 전체"를 돌려준다(화면이 무한스크롤이라 그렇다). 예를 들어
pageUnit=3이면 pageIndex 1/2/3의 응답 행수가 3/6/9다. 직접 호출할 때 페이지별
응답을 이어 붙이면 중복이 생기므로, 마지막 응답만 쓰면 된다.
client.fetch()는 이 규칙에 맞춰 페이지를 이어 붙이지 않고 교체한다.
"""

# 상장시장 필터(scMktId). 화면의 라디오 버튼 값 그대로다.
MARKETS = {
    "ALL": "",
    "": "",
    "KOSPI": "STK",
    "STK": "STK",
    "KOSDAQ": "KSQ",
    "KSQ": "KSQ",
}

# jqGrid 규약상 모든 행에 섞여 오는 eGovFrame 페이징/검색/감사 필드.
# 데이터가 아니므로 drop_paging_fields 후처리에서 제거한다.
PAGING_FIELDS = (
    "nowPage",
    "pagePerRow",
    "pagePerBlock",
    "pageIndex",
    "pageUnit",
    "pageSize",
    "firstIndex",
    "lastIndex",
    "recordCountPerPage",
    "rnum",
    "attachedFileId",
    "searchKeyword",
    "searchKeywordEn",
    "searchCondition",
    "authorCodeNot",
    "sortKey",
    "sortType",
    "scBeginDe",
    "scEndDe",
    "scAggDd",
    "scMktId",
    "registUserId",
    "updateUserId",
    "updateDt",
    # 행 안에도 totalCnt가 있지만 항상 0이다. 전체 건수는 응답 봉투의 records를 쓴다.
    # (client.fetch()가 df.attrs["records"]에 넣어 준다.)
    "totalCnt",
)

# epoch milliseconds로 오는 필드. KST(+09:00) datetime으로 바꾼다.
# (그냥 두면 결측이 있는 순간 float64가 되어 1.786533e+12처럼 보인다.)
EPOCH_MS_FIELDS = ("registDt",)

# 숫자로 변환할 필드. 날짜/시각/코드(aggDd, nowDd, creTime, isuSrdCd ...)는
# 앞자리 0이 의미를 가지므로 문자열로 남긴다.
NUMERIC_FIELDS = (
    "basePrc",
    "cspr",
    "curPrc",
    "contrastPrc",
    "upDownRate",
    "oppr",
    "hgpr",
    "lwpr",
    "accTdQty",
    "accTrval",
    "lsstCt",
    "totalIsuCnt",
    "totalAccTdQty",
    "totalAccTrval",
    "upRateCnt",
    "downRateCnt",
    "zeroRateCnt",
    "totalPrc",
)

# rename_korean 후처리용 라벨. 화면 그리드(colNames)에서 확인된 것과
# KRX 표준 약어에서 뜻이 분명한 것만 넣었다.
# 매핑에 없는 필드는 원래 이름 그대로 남는다.
COLUMN_LABELS = {
    "aggDd": "집계일자",
    "mktId": "상장시장코드",
    "mktNm": "상장시장",
    "isuCd": "표준코드",
    "isuSrdCd": "단축코드",
    "isuAbwdNm": "종목명",
    "isuEnawNm": "종목영문명",
    "basePrc": "기준가",
    "nowDd": "조회시점일자",
    "nowTime": "조회시점시각",
    "creTime": "생성시각",
    "registDt": "적재시각",
    "cspr": "종가",
    "curPrc": "현재가",
    "contrastPrc": "대비",
    "upDownRate": "등락률",
    "oppr": "시가",
    "hgpr": "고가",
    "lwpr": "저가",
    "accTdQty": "거래량",
    "accTrval": "거래대금",
    "cptrTrdPmsnCd": "거래가능시장코드",
    "cptrTrdPmsnCdNm": "거래가능시장",
    "trdIpsbRsn": "거래불가사유",
}

# 넥스트레이드가 두 화면 모두에서 항상 null 또는 0으로 채워 보내는 필드들.
# 화면 그리드에도 표시되지 않는다. 값을 기대하지 말 것.
UNUSED_FIELDS = (
    "brdId",          # 항상 "G1"
    "trdPmsnYn",      # 항상 null
    "tdhlYn",         # 항상 null
    "trdcapYn",       # 정규시장은 항상 "N", 종가매매는 null
    "trdvapBegnDd",   # 항상 공백 문자열
    "lsstCt",         # 항상 0
    "totalIsuCnt",    # 이하 정규시장 응답에만 있고 항상 0 (시장 전체 집계용 자리)
    "totalAccTdQty",
    "totalAccTrval",
    "upRateCnt",
    "downRateCnt",
    "zeroRateCnt",
    "totalPrc",
)

_GRID_DEFAULTS = {
    "_search": "false",
    "sidx": "",
    "sord": "asc",
    # 화면은 20씩 끊어 받지만, 한 번에 전부 받는 편이 빠르다.
    # 이보다 행이 많으면 client.fetch()가 다음 페이지를 이어 받는다.
    "pageUnit": 10000,
    "pageIndex": 1,
    "scMktId": "",
    "searchKeyword": "",
}

ENDPOINTS = {
    # 거래현황 > 정규시장. 종목별 시가/고가/저가/현재가와 거래가능시장·거래불가사유까지.
    # scAggDd를 생략하면 당일 실시간 스냅샷이 온다.
    "regular_market": {
        "path": "brdinfoTime/brdinfoTimeList.do",
        "list_key": "brdinfoTimeList",
        "referer": "/menu/transactionStatusMain/menuList.do",
        "defaults": dict(_GRID_DEFAULTS),
        "post": ["drop_paging_fields", "coerce_types"],
        "screen": "거래현황 > 정규시장",
    },
    # 거래현황 > 종가매매. 종가(cspr)·거래량·거래대금만 있는 축약된 스냅샷이다.
    # 정규시장과 달리 거래가능시장/거래불가사유 계열은 전부 null로 온다.
    "closing_price": {
        "path": "brdinfoEnd/brdinfoEndList.do",
        "list_key": "brdinfoEndList",
        "referer": "/menu/transactionStatusClosing/menuList.do",
        "defaults": dict(_GRID_DEFAULTS),
        "post": ["drop_paging_fields", "coerce_types"],
        "screen": "거래현황 > 종가매매",
    },
}


def get(name: str) -> dict:
    from .exceptions import UnknownEndpointError

    if name not in ENDPOINTS:
        raise UnknownEndpointError(
            f"Unknown endpoint: {name!r}. Available: {sorted(ENDPOINTS)}"
        )
    return ENDPOINTS[name]
