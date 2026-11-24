# 1-01 일별 NXT vs KRX 거래량 비중

[노트북](01_daily_share.ipynb) · [Colab에서 열기](https://colab.research.google.com/github/beaten-by-the-market/nxt-data-api/blob/main/scenarios/1_nxt_vs_krx/01_daily_share.ipynb) · 원본: `krxnewsscrap/krxnxtplotly.py`, `krxvsnxt.ipynb` · 구분: **각색**

## 한 줄 요약
하루를 골라 종목마다 NXT 거래량과 KRX 거래량을 6자리 코드로 맞춰 보고, 시장(KOSPI·KOSDAQ)별 NXT 점유율과 NXT 비중이 높은 종목을 뽑습니다.

## 이렇게 물어보세요
- "어제 넥스트레이드 거래량이 KRX 대비 얼마나 됐어?"
- "NXT 비중이 제일 높은 종목은?"
- "코스닥이 코스피보다 NXT 비중이 높아?"

## 데이터와 정의
| 항목 | 출처 / 정의 |
|---|---|
| NXT 거래량 | `regular_market` + `closing_price` + `block_trade`(대량·바스켓) 거래량 합. 세 화면은 서로 겹치지 않습니다 |
| NXT 거래대금 | `regular_market` + `closing_price`. 대량·바스켓 화면에는 거래대금이 없어 빠집니다 |
| KRX 거래량·거래대금 | `krx_data_api` `all_stock_price`의 `ACC_TRDVOL`·`ACC_TRDVAL` (영문 코드 컬럼을 헬퍼가 명시적으로 매핑) |
| 조인 | 6자리 단축코드. NXT `isuSrdCd`(`A005930`)의 `A`를 떼서 KRX `ISU_SRT_CD`와 맞춤. outer join 후 `NXT·KRX` / `KRX만` / `NXT만`으로 표시 |
| **NXT점유율** | NXT ÷ (NXT + KRX). 두 거래소 합계 중 NXT 몫, 0~100% |
| NXT/KRX | NXT ÷ KRX. 원본 앱의 "비중". KRX보다 많으면 100%를 넘음 |
| 모집단 | **NXT 거래종목**(NXT에서 거래되는 종목끼리) / **시장 전체**(KOSPI·KOSDAQ 전 종목, 코넥스 제외) |

## 결과 예시 (2026-11-24, 노트북 실행값)
| 모집단 | 시장 | 종목수 | NXT점유율(거래량) | NXT/KRX | NXT점유율(거래대금) |
|---|---|---|---|---|---|
| NXT 거래종목 | KOSPI | 335 | 36.7% | 58.0% | 42.4% |
| NXT 거래종목 | KOSDAQ | 267 | 46.9% | 88.4% | 46.2% |
| NXT 거래종목 | 합계 | 602 | 40.8% | 69.0% | 43.0% |
| 시장 전체 | KOSPI | 935 | 21.2% | 26.9% | 39.7% |
| 시장 전체 | KOSDAQ | 1,837 | 9.2% | 10.1% | 25.2% |
| 시장 전체 | 합계 | 2,772 | 13.2% | 15.3% | 36.3% |

- KRX 2,879종목 중 602종목이 NXT에서도 거래됐고, NXT에만 있는 종목은 0개였습니다(ISIN도 전부 일치).
- 602종목 중 72종목은 NXT 거래량이 KRX보다 많았습니다(NXT/KRX > 100%). 합계 거래대금 100억 이상 중 NXT점유율 1위는 서울반도체(76.1%).
- NXT 거래대금 1·2위는 SK하이닉스(3.4조, 점유율 44.3%)·삼성전자(3.1조, 48.4%).
- 그날 NXT 거래량의 99.999%가 정규시장 화면, 종가매매는 1,312주, 대량·바스켓은 0건이었습니다.

## 결과 읽는 법
- 언론의 "NXT 비중"은 보통 **NXT 거래종목** 기준입니다. **시장 전체** 기준은 NXT가 다루지 않는 소형주 거래까지 분모에 넣어 훨씬 낮고, 특히 코스닥 거래량 기준(9.2%)이 낮습니다.
- 시장 전체 기준에서 거래대금 점유율이 거래량 점유율보다 높은 것은 NXT 종목이 대형·고가주에 몰려 있기 때문입니다.
- 종목별 순위는 합계 거래대금 100억 미만 종목을 뺍니다. 거래가 거의 없는 종목은 점유율이 극단으로 튑니다(예: 아이티엠반도체 98.6%, KRX 6,809주).

## 주의·한계
- **NXT 거래량은 애프터마켓(~20:00)까지 포함합니다**(정규시장 스냅샷 적재 20:05). 프리마켓도 같은 화면에 있는 것으로 보이지만 세션별로 쪼개 확인하지 않았습니다. KRX 쪽 [12001] 거래량에 시간외·대량이 어디까지 들어가는지도 따로 확인하지 않았습니다.
- 두 거래소 숫자는 배타적입니다(`docs/NXT_거래현황_API_정리.md` §2.1). 전체 시장 거래량은 KRX + NXT입니다.
- NXT 거래대금에는 대량·바스켓 대금이 없습니다. 대량매매는 드뭅니다(2026-08-03~11-24 조회 결과 0건).
- NXT `거래가능 = 거래불가`(투자경고·위험 등) 종목은 NXT 거래량이 0이라 점유율 0%로 나옵니다. 6장에서 따로 보여 줍니다(2026-11-24: NHN).
- KRX `all_stock_price`는 휴장일에 값이 전부 `-`로 옵니다(2026-11-22 확인). 헬퍼 `krx_prices()`는 이때 오류를 냅니다.

## 쓰는 함수
`nxt_data_api.fetch_range`(`regular_market`, `closing_price`, `block_trade`), `krx_data_api.fetch("all_stock_price")` — 공통 헬퍼 `nxt_volume()`, `krx_prices()`, `compare()`, `share_summary()` (`scenarios/_tools/nxt_helper.py`)
