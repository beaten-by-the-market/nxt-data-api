# nxt-data-api

넥스트레이드(`nextrade.co.kr`) 거래현황 조회를 endpoint 이름 기반 `fetch()` 함수로 감싼 Python 패키지입니다. [krx-data-api](https://github.com/beaten-by-the-market/krx-data-api)와 같은 구조(`transport` / `endpoints` / `client` / `exceptions`)를 따릅니다.

- 화면의 jqGrid 백엔드(`*List.do`)를 그대로 호출해 DataFrame으로 돌려줍니다.
- **로그인이 필요 없습니다.** KRX 정보데이터시스템과 달리 OTP·세션 인증이 없어 `.env` 설정이 없습니다.
- 하루치 스냅샷 API이므로, 기간 조회는 `fetch_range()`가 영업일을 돌며 이어 붙입니다.

원시 API 계약, 함정, KRX 데이터와 대조해 확인한 숫자의 의미는 [docs/NXT_거래현황_API_정리.md](docs/NXT_거래현황_API_정리.md)에 정리했습니다. **넥스트레이드 거래량은 KRX 거래량과 배타적입니다(합산이 아닙니다)** — 이 데이터로 분석하기 전에 읽어 보세요.

## 설치

```bash
pip install git+https://github.com/beaten-by-the-market/nxt-data-api.git
```

## 사용 예시

```python
from nxt_data_api import fetch, fetch_range

# 거래현황 > 정규시장 (시가·고가·저가·현재가·거래가능시장)
df = fetch("regular_market", date="20260812")

# 거래현황 > 종가매매 (종가·거래량·거래대금)
df = fetch("closing_price", date="20260812")

# 날짜를 생략하면 당일 실시간 스냅샷
df = fetch("regular_market")

# 시장 / 종목 필터
df = fetch("regular_market", date="20260812", market="KOSDAQ")
df = fetch("regular_market", date="20260812", keyword="005930")   # 코드 또는 종목명

# 기간 조회 — 영업일을 하루씩 돌며 이어 붙입니다 (휴장일은 0건이라 자연히 빠짐)
df = fetch_range("regular_market", "20260801", "20260812")
print(df.attrs["empty_dates"])   # 데이터가 없던 날짜
```

`date`는 `"20260812"` / `"2026-08-12"` / `datetime.date(2026, 8, 12)`를 모두 받습니다. `market`은 `"ALL"` / `"KOSPI"`(=`STK`) / `"KOSDAQ"`(=`KSQ`)입니다. 원시 파라미터(`scAggDd`, `scMktId`, `searchKeyword`, `pageUnit` …)를 직접 줘도 됩니다.

응답 봉투 정보는 `df.attrs`에 담깁니다.

```python
df.attrs
# {'endpoint': 'regular_market', 'screen': '거래현황 > 정규시장',
#  'records': 608, 'set_time': '2026-08-12 20:05', 'pages': 1}
```

목록과 상세 정보는 프로그래밍 방식으로 확인할 수 있습니다.

```python
from nxt_data_api import list_endpoints, endpoint_info

print(list_endpoints())            # ['closing_price', 'regular_market']
print(endpoint_info("regular_market"))
```

## 엔드포인트 카탈로그

| 이름 | 경로 | 화면 |
|------|------|------|
| `regular_market` | `brdinfoTime/brdinfoTimeList.do` | 거래현황 > 정규시장 |
| `closing_price` | `brdinfoEnd/brdinfoEndList.do` | 거래현황 > 종가매매 |

두 화면 모두 조회일자(`scAggDd`) 하루치를 줍니다. 넥스트레이드 개장일인 **2025-03-04**(시범 10종목)부터 조회되고, 그 이전 날짜나 휴장일은 0건이 옵니다.

## 컬럼

화면 그리드에 표시되는 컬럼과 원시 필드명의 대응입니다.

| 필드 | 뜻 | `regular_market` | `closing_price` |
|------|-----|:---:|:---:|
| `aggDd` | 집계일자 | ● | ● |
| `mktId` / `mktNm` | 상장시장 코드 / 이름 (`STK`=KOSPI, `KSQ`=KOSDAQ) | ● | ● |
| `isuCd` | 표준코드 (ISIN) | ● | ● |
| `isuSrdCd` | 단축코드 (`A005930`) | ● | ● |
| `isuAbwdNm` / `isuEnawNm` | 종목명 / 영문명 | ● | ● |
| `basePrc` | 기준가 | ● | ● |
| `curPrc` | 현재가 | ● | |
| `cspr` | 종가 | | ● |
| `contrastPrc` / `upDownRate` | 대비 / 등락률(%) | ● | |
| `oppr` / `hgpr` / `lwpr` | 시가 / 고가 / 저가 | ● | |
| `accTdQty` / `accTrval` | 거래량 / 거래대금 | ● | ● |
| `cptrTrdPmsnCdNm` | 거래가능시장 (`전체` / `거래불가`) | ● | (null) |
| `trdIpsbRsn` | 거래불가사유 (`거래정지`, `투자경고/위험` …) | ● | (null) |
| `creTime` / `nowDd` / `nowTime` | 생성시각 / 조회시점 일자·시각 | ● | 일부 |
| `registDt` | 적재시각 (KST datetime) | ● | ● |

가격·수량 필드는 숫자로 변환되고, 날짜·시각·코드 필드는 앞자리 0을 보존하기 위해 문자열로 남습니다. epoch ms로 오는 `registDt`만 KST(+09:00) datetime으로 바뀝니다.

넥스트레이드가 **항상 null 또는 0으로 채워 보내는 미사용 필드**(`brdId`, `trdPmsnYn`, `tdhlYn`, `trdcapYn`, `trdvapBegnDd`, `lsstCt`, `total*`, `upRateCnt`, `downRateCnt`, `zeroRateCnt`)도 응답에 섞여 옵니다. `endpoints.UNUSED_FIELDS`에 정리돼 있고, 아래 후처리로 뺄 수 있습니다.

## 후처리

`fetch(..., post=[...])`로 후처리 파이프라인을 바꿀 수 있습니다. 기본값은 `["drop_paging_fields", "coerce_types"]`입니다.

| 이름 | 하는 일 | 기본 |
|------|---------|:---:|
| `drop_paging_fields` | 모든 행에 섞여 오는 jqGrid 페이징·검색·감사 필드 제거 | ● |
| `coerce_types` | 가격·수량 필드를 숫자로, 문자열 공백 정리 | ● |
| `drop_unused` | 항상 null/0인 미사용 필드 제거 | |
| `rename_korean` | 뜻이 분명한 필드에 한글 컬럼명 부여 | |

```python
df = fetch(
    "regular_market",
    date="20260812",
    post=["drop_paging_fields", "coerce_types", "drop_unused", "rename_korean"],
)
# 집계일자 / 상장시장 / 단축코드 / 종목명 / 현재가 / 대비 / 등락률 / ...
```

`register_post_processor("이름", func)`로 커스텀 후처리도 추가할 수 있습니다.

## 페이지네이션 (주의)

넥스트레이드의 `pageIndex`는 **누적**입니다. `pageIndex=N`이 "N번째 페이지"가 아니라 "1~N페이지 전체"를 돌려줍니다(화면이 무한스크롤이라 그렇습니다). `pageUnit=3`이면 `pageIndex` 1/2/3의 응답 행수가 3/6/9입니다.

`fetch()`는 이 규칙에 맞춰 페이지를 **이어 붙이지 않고 교체**하며, 기본 `pageUnit=10000`이라 대개 한 번의 호출로 전부 받습니다. 직접 호출할 때 페이지별 응답을 concat하면 중복이 생기니 주의하세요.

## 직접 호출

카탈로그에 없는 화면도 transport 함수로 직접 호출할 수 있습니다.

```python
import pandas as pd
from nxt_data_api import transport

payload = transport.grid_post(
    "brdinfoTime/brdinfoTimeList.do",
    {"pageUnit": 10000, "pageIndex": 1, "scAggDd": "20260812"},
    referer="/menu/transactionStatusMain/menuList.do",
)
df = pd.DataFrame(payload["brdinfoTimeList"])
```

응답 `Content-Type`이 `text/html`이지만 본문은 JSON입니다. `grid_post()`가 UTF-8로 디코딩해 dict로 돌려줍니다.

## 테스트

```bash
pytest tests/test_client.py          # 오프라인 (요청 조립·후처리 검증)
pytest                               # 넥스트레이드 실호출 포함
NXT_SKIP_LIVE=1 pytest               # 실호출 테스트 건너뛰기
```

## 프로젝트 구조

```text
nxt_data_api/
├── __init__.py        공개 API re-export
├── transport.py       *List.do POST 저수준 호출
├── endpoints.py       endpoint 카탈로그 + 필드 메타데이터
├── client.py          fetch() / fetch_range()와 후처리 레지스트리
└── exceptions.py
```
