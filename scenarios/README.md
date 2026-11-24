# 분석 시나리오 노트북

`nxt-data-api`(넥스트레이드)와 [`krx-data-api`](https://github.com/beaten-by-the-market/krx-data-api)(KRX 정보데이터시스템)를 함께 써서 질문 하나에 답하는 노트북 모음입니다. 모두 Colab에서 바로 열 수 있고, 저장된 출력은 실제 데이터로 실행한 결과입니다.

## 목록

| 번호 | 시나리오 | 질문 예시 | 원본 |
|---|---|---|---|
| [1-01](1_nxt_vs_krx/01_daily_share.md) | 일별 NXT vs KRX 거래량 비중 | "어제 NXT 거래량이 KRX 대비 얼마나 됐어?", "NXT 비중이 제일 높은 종목은?" | `krxnewsscrap/krxnxtplotly.py`, `krxvsnxt.ipynb` |
| [1-02](1_nxt_vs_krx/02_share_trend.md) | NXT 점유율 추이 (일별·종목별 기간 합계·개장 이후 월별) | "최근 석 달 NXT 비중이 늘었어?", "개장 이후 어떻게 변했어?" | `krxnewsscrap/krxvsnxt_cumul.ipynb` |

## 공통 정의

- **NXT 거래량** = `regular_market` + `closing_price` + `block_trade` 거래량 합. 세 화면은 겹치지 않습니다. 정규시장 화면은 애프터마켓(~20:00)까지 포함합니다.
- **KRX 거래량** = `all_stock_price`([12001] 전종목시세)의 `ACC_TRDVOL`. KRX에서 체결된 것만이며 NXT와 배타적입니다.
- **NXT점유율** = NXT ÷ (NXT + KRX). 원본 앱의 "비중"은 NXT ÷ KRX이고 노트북에 `NXT/KRX`로 함께 보여 줍니다.
- 조인은 6자리 단축코드(NXT `isuSrdCd`의 `A` 제거 = KRX `ISU_SRT_CD`)로 합니다.

자세한 API 동작은 [docs/NXT_거래현황_API_정리.md](../docs/NXT_거래현황_API_정리.md)를 보세요.

## Colab에서 실행

1. 목록의 노트북을 열고 상단 "Colab에서 열기" 배지를 누릅니다.
2. 왼쪽 🔑(Secrets)에 `KRX_ID`, `KRX_PW`를 등록하고 노트북 액세스를 켭니다. KRX는 2026-09부터 로그인해야 데이터를 줍니다. 넥스트레이드는 로그인이 필요 없습니다.
3. "0. 준비"의 두 셀을 실행하면 `nxt-data-api`와 `krx-data-api`를 GitHub에서 설치하고 공통 헬퍼를 불러옵니다.

## 로컬에서 고치고 다시 만들기

`.ipynb`를 직접 고치지 말고 원본을 고친 뒤 빌드합니다.

```text
scenarios/
├── _src/<유형>/NN_이름.py   노트북 원본 (# %% 셀 구분, 첫 셀은 제목 markdown)
├── _tools/build.py          원본 → 실행된 .ipynb (Colab 배지·준비 셀 삽입)
├── _tools/nxt_helper.py     모든 노트북의 준비 셀에 들어가는 공통 헬퍼
├── _tools/show.py           실행된 노트북의 출력을 터미널에서 확인
└── <유형>/NN_이름.ipynb, NN_이름.md
```

```bash
pip install nbformat nbclient ipykernel matplotlib
python scenarios/_tools/build.py                    # 전체 다시 실행
python scenarios/_tools/build.py 1_nxt_vs_krx/01    # 경로에 이 문자열이 든 원본만
python scenarios/_tools/build.py --no-exec          # 실행 없이 노트북만 생성
python scenarios/_tools/show.py scenarios/1_nxt_vs_krx/01_daily_share.ipynb
```

빌드는 레포 루트에서 노트북을 실행하므로 이 레포의 `nxt_data_api`를 그대로 씁니다. `krx_data_api`는 설치된 패키지를 쓰고, `KRX_ID`/`KRX_PW`를 환경변수 → 작업 폴더 `.env` → (편집 가능 설치라면) krx-data-api 레포의 `.env` 순서로 찾습니다. 계정 정보는 출력에 남지 않습니다. `nxt_helper.py`를 고치면 모든 노트북을 다시 빌드하세요.
