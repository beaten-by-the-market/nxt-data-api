# 넥스트레이드 거래현황 API 정리

`nxt-data-api`가 감싸는 넥스트레이드(NXT) 거래현황 API의 원시 계약과, KRX 데이터와 대조해 확인한 숫자의 의미를 정리한다. 다른 세션에서 이 데이터로 검증 작업을 할 때 먼저 읽으면 된다.

## 1. 무엇을 주는 API인가

넥스트레이드는 2025년 3월 4일 개장한 국내 대체거래소(ATS)다. 이 API는 **넥스트레이드에서 체결된 거래**의 종목별 일별 스냅샷을 준다. 두 화면이 있다.

| 패키지 이름 | 원시 경로 | 화면 | 내용 |
|---|---|---|---|
| `regular_market` | `POST /brdinfoTime/brdinfoTimeList.do` | 거래현황 > 정규시장 | 시가·고가·저가·현재가·대비·등락률·거래량·거래대금·거래가능시장·거래불가사유 |
| `closing_price` | `POST /brdinfoEnd/brdinfoEndList.do` | 거래현황 > 종가매매 | 종가·거래량·거래대금 |

로그인·OTP·세션 쿠키가 전부 필요 없다. 세션 없이 곧바로 POST해도 정상 응답한다.

## 2. KRX 데이터와의 관계 (검증 완료)

**2026-08-12 하루치를 `krx-data-api`의 `all_stock_price`(전종목시세)와 종목코드로 조인해 확인했다.** NXT 608종목 전부가 KRX 데이터에 매칭됐다.

### 2.1 두 거래소의 수치는 서로 배타적이다 (합산이 아니다)

| 검증 항목 | 결과 |
|---|---|
| NXT 거래량 / KRX 거래량 비율 (중앙값) | 0.545 |
| 같은 비율이 1을 넘는 종목 수 | **101종목** (최대 15.4배) |
| 608종목 합계 거래대금 | NXT 18.3조 / KRX 26.4조 |

비율이 1보다 큰 종목이 101개나 된다는 것은 **KRX 정보데이터시스템의 거래량이 KRX 체결분만, 넥스트레이드의 거래량이 NXT 체결분만 담고 있다**는 뜻이다. 어느 한쪽이 다른 쪽을 포함하는 관계가 아니다.

> 검증 작업에서 "전체 시장 거래량"이 필요하면 **KRX + NXT를 더해야 한다.** 어느 한쪽만 쓰면 과소집계된다.

### 2.2 정규시장의 현재가는 KRX 종가가 아니다

| 검증 항목 | 일치율 |
|---|---|
| NXT `curPrc` == KRX 종가 | 5.4% |
| NXT `oppr` == KRX 시가 | 6.7% |
| NXT `hgpr` == KRX 고가 | 23.4% |
| NXT `lwpr` == KRX 저가 | 43.4% |

별개 거래소에서 독립적으로 체결된 가격이다. 유동성이 큰 종목에서 고가·저가가 우연히 일치하는 경우가 있을 뿐이다. NXT 정규시장은 KRX보다 늦게(애프터마켓 포함) 끝나므로 `curPrc`는 그 시점의 마지막 체결가다.

예시 — 삼성전자 2026-08-12:

| | KRX | NXT |
|---|---|---|
| 시가 | 243,500 | 242,000 |
| 고가 | 260,500 | 260,500 |
| 저가 | 241,000 | 241,000 |
| 종가 / 현재가 | 255,500 | 258,000 |
| 등락률 | 6.68% | 7.72% |
| 거래량 | 27,102,479 | 19,366,585 |

### 2.3 종가매매의 종가는 KRX 종가와 100% 일치한다

`closing_price`의 `cspr`은 조회한 81종목 **전부**가 KRX 종가와 일치했다. 종가매매 세션은 KRX 종가로 체결되는 세션이므로, `cspr`은 가격 정보가 아니라 **체결 기준가**로 봐야 한다. 이 화면에서 의미 있는 값은 `accTdQty`(거래량)와 `accTrval`(거래대금)이다.

### 2.4 기준가는 전일 KRX 종가다

삼성전자 2026-08-12 `basePrc` = 239,500이고, KRX의 전일 종가(255,500 − 대비 16,000) = 239,500으로 일치한다. `upDownRate`도 `(curPrc − basePrc) / basePrc`와 맞는다 (258,000 → 7.72%).

## 3. 원시 HTTP 계약

```
POST https://nextrade.co.kr/brdinfoTime/brdinfoTimeList.do
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With: XMLHttpRequest
Referer: https://nextrade.co.kr/menu/transactionStatusMain/menuList.do

_search=false&pageUnit=20&pageIndex=1&sidx=&sord=asc
&scAggDd=20260812&scMktId=&searchKeyword=
```

### 요청 파라미터

| 파라미터 | 뜻 | 값 |
|---|---|---|
| `scAggDd` | 조회일자 | `YYYYMMDD`. **생략하면 당일 실시간 스냅샷** |
| `scMktId` | 상장시장 | `""`(전체) / `STK`(KOSPI) / `KSQ`(KOSDAQ) |
| `searchKeyword` | 종목 필터 | 단축코드 6자리 또는 종목명 일부 |
| `pageUnit` | 페이지당 행수 | 화면은 20. 10000을 주면 한 번에 전부 온다 |
| `pageIndex` | 페이지 번호 | **누적이다. 아래 4.1 참고** |
| `_search`, `sidx`, `sord` | jqGrid 관성 | 없어도 동작한다 |

### 응답 봉투

```json
{"records": 608, "totalCnt": 608, "total": 1, "page": 1,
 "setTime": "2026-08-12 20:05",
 "brdinfoTimeList": [ ... ]}
```

- `records` / `totalCnt` = 전체 행수, `total` = 페이지 수, `page` = 현재 페이지
- `setTime`은 `regular_market`에만 있다. 스냅샷 집계 시각이다. 데이터가 없는 날은 시각 없이 날짜만 온다 (`"2026-08-15"`)
- 행 배열의 키는 화면마다 다르다: `brdinfoTimeList` / `brdinfoEndList`

## 4. 함정 4가지

### 4.1 `pageIndex`는 누적이다 — 페이지를 이어 붙이면 중복된다

넥스트레이드는 `pageIndex=N`에 "N번째 페이지"가 아니라 **"1~N페이지 전체"**를 돌려준다. 화면이 무한스크롤이라 그렇다. `pageUnit=3`으로 실측한 결과:

| pageIndex | 응답 행수 | 내용 |
|---|---|---|
| 1 | 3 | 1~3번째 |
| 2 | 6 | 1~6번째 |
| 3 | 9 | 1~9번째 |
| 4 | 10 | 전부 (records=10) |
| 5 | 10 | 전부 (더 안 늘어남) |

페이지별 응답을 concat하면 중복이 생긴다. `nxt_data_api.client.fetch()`는 이어 붙이지 않고 **마지막 응답으로 교체**한다. 직접 호출한다면 `pageUnit`을 크게 줘서 한 번에 받는 게 안전하다.

### 4.2 `Content-Type`이 `text/html`이지만 본문은 JSON이다

`text/html;charset=UTF-8`로 오지만 내용은 JSON이다. UTF-8로 디코딩해서 파싱하면 된다.

### 4.3 모든 행에 jqGrid 페이징 필드가 섞여 온다

행마다 `nowPage`, `pageUnit`, `rnum`, `firstIndex`, `searchKeyword`, `scAggDd`, `registUserId` 등 20여 개의 eGovFrame 페이징·검색·감사 필드가 데이터와 함께 온다. 전부 무의미하다. 행 안의 `totalCnt`도 항상 0이니 봉투의 `records`를 써야 한다. (`endpoints.PAGING_FIELDS`)

### 4.4 항상 null/0으로만 오는 필드가 있다

`brdId`(항상 `"G1"`), `trdPmsnYn`, `tdhlYn`, `trdcapYn`, `trdvapBegnDd`(공백), `lsstCt`, `totalIsuCnt`, `totalAccTdQty`, `totalAccTrval`, `upRateCnt`, `downRateCnt`, `zeroRateCnt`, `totalPrc`. 이름만 보고 값을 기대하면 안 된다. (`endpoints.UNUSED_FIELDS`)

특히 `closing_price`는 `cptrTrdPmsnCd`·`cptrTrdPmsnCdNm`·`trdIpsbRsn`·`trdcapYn`까지 전부 null이다. 거래가능시장·거래불가사유는 `regular_market`에서만 채워진다.

## 5. 필드 사전

| 필드 | 뜻 | `regular_market` | `closing_price` |
|---|---|:---:|:---:|
| `aggDd` | 집계일자 (`YYYYMMDD`) | ● | ● |
| `mktId` / `mktNm` | `STK`=KOSPI, `KSQ`=KOSDAQ | ● | ● |
| `isuCd` | 표준코드 (ISIN, `KR7005930003`) | ● | ● |
| `isuSrdCd` | 단축코드 (**`A` 접두사 포함**, `A005930`) | ● | ● |
| `isuAbwdNm` / `isuEnawNm` | 종목명 / 영문명 | ● | ● |
| `basePrc` | 기준가 = 전일 KRX 종가 | ● | ● |
| `curPrc` | NXT 현재가(마지막 체결가) | ● | |
| `cspr` | 종가 = KRX 종가와 동일 | | ● |
| `contrastPrc` / `upDownRate` | 대비 / 등락률(%) — `basePrc` 기준 | ● | |
| `oppr` / `hgpr` / `lwpr` | NXT 시가 / 고가 / 저가 | ● | |
| `accTdQty` / `accTrval` | **NXT 거래량 / 거래대금** | ● | ● |
| `cptrTrdPmsnCdNm` | 거래가능시장: `전체`(코드 7) / `거래불가`(코드 0) | ● | (null) |
| `trdIpsbRsn` | 거래불가사유: `거래정지`, `투자경고/위험` | ● | (null) |
| `creTime` | 생성시각 (`HHMMSS`, 예 `200500`) | ● | |
| `nowDd` / `nowTime` | 조회 시점의 서버 일자·시각 | ● | ● |
| `registDt` | 적재시각 (epoch ms → 패키지가 KST datetime으로 변환) | ● | ● |

단축코드에 `A` 접두사가 붙는 점을 주의. KRX 데이터와 조인하려면 `isuSrdCd.str[1:]`로 떼거나, 접두사 없는 `isuCd`(ISIN)로 조인한다.

## 6. 데이터 가용 범위

- **2025-03-04(개장일)부터** 조회된다. 개장일은 시범 10종목뿐이다 (와이지엔터, 코오롱인더, LG유플러스, S-Oil, 에스에프에이, 동국제약, 컴투스, 롯데쇼핑, 제일기획, 골프존).
- 하루씩만 조회된다. 기간 조회 API가 없어서 `fetch_range()`가 영업일을 하루씩 돌며 이어 붙인다.
- 휴장일·주말·개장 전 날짜는 **HTTP 200에 0건**으로 온다. 에러가 아니다.
- 잘못된 날짜 문자열도 200에 0건으로 온다 (`scAggDd=bad-date` → `setTime: "bad--da-te"`). **서버가 입력을 검증하지 않으니 날짜 오타가 조용히 빈 결과가 된다.** 패키지의 `date=` 별칭은 `YYYYMMDD` 8자리를 강제해서 이걸 막는다.
- 종목 수는 날짜마다 다르다. 2026-08-12 기준 정규시장 608종목, 종가매매 81종목.

## 7. 패키지 사용법

```python
from nxt_data_api import fetch, fetch_range

df = fetch("regular_market", date="20260812")
df = fetch("closing_price", date="20260812", market="KOSDAQ")
df = fetch("regular_market")                              # 당일 실시간
df = fetch_range("regular_market", "20260801", "20260812")

df.attrs   # {'records': 608, 'set_time': '2026-08-12 20:05', 'pages': 1, ...}
```

기본 후처리는 페이징 필드 제거 + 타입 변환이다. 미사용 필드까지 빼고 한글 컬럼명을 원하면:

```python
df = fetch("regular_market", date="20260812",
           post=["drop_paging_fields", "coerce_types", "drop_unused", "rename_korean"])
```

가격·수량은 숫자, 날짜·시각·코드는 앞자리 0 보존을 위해 문자열로 남는다.

## 8. 확인하지 않은 것

검증 작업 전에 필요하면 직접 확인할 것.

- **장중 스냅샷의 동작.** 위 확인은 전부 장 종료 후(`creTime` 200500)에 했다. 장중에 `scAggDd` 없이 호출하면 `creTime`이 어떻게 변하는지, 갱신 주기가 얼마인지 확인 안 했다.
- **과거 날짜 데이터의 확정 여부.** 같은 날짜를 다시 조회했을 때 값이 변하지 않는지 확인 안 했다.
- **종가매매 종목 수가 적은 이유.** 정규시장 608종목 대비 종가매매는 81종목뿐이다. 종가매매 세션에 실제 체결이 있었던 종목만 나오는 것으로 보이나 확정하지 않았다.
- **다른 세션 화면의 존재 여부.** 넥스트레이드는 프리마켓/메인/애프터마켓 세션을 운영하는데, 세션별 화면이 따로 있는지 찾아보지 않았다. 이 두 화면만 확인했다.
- `cptrTrdPmsnCd`의 `7`/`0` 외 다른 코드값.
