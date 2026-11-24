# ── NXT·KRX 헬퍼 (모든 시나리오 노트북 공통) ─────────────────────────────
# NXT(넥스트레이드): nxt_data_api — 로그인 불필요.
# KRX(정보데이터시스템): krx_data_api — 2026-09부터 로그인 필요.
#   Colab: 왼쪽 🔑(Secrets)에 KRX_ID, KRX_PW 를 넣고 "노트북 액세스"를 켜세요. 값은 출력하지 않습니다.
#   로컬: 환경변수 → 작업 폴더 .env → (편집 가능 설치라면) krx-data-api 레포의 .env 순서로 찾습니다.
import os, sys, time
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

IN_COLAB = "google.colab" in sys.modules
if IN_COLAB:
    from google.colab import userdata
    for _k in ("KRX_ID", "KRX_PW"):
        try:
            _v = userdata.get(_k)
            if _v:
                os.environ[_k] = _v
        except Exception as _e:  # SecretNotFoundError / NotebookAccessError
            print(f"Colab Secrets에서 {_k}를 읽지 못했습니다 ({type(_e).__name__}). 🔑에 등록하고 액세스를 켜세요.")

from nxt_data_api import fetch as nxt_fetch, fetch_range as nxt_fetch_range
from krx_data_api import fetch as krx_fetch
from krx_data_api.daily_snapshots import trading_days  # KRX 매매거래일 목록 (삼성전자 시세추이의 일자)

pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 40)

MARKETS = ["KOSPI", "KOSDAQ"]  # NXT는 코넥스 종목을 거래하지 않습니다


def _num(s):
    """'1,234' / '-' / '' 같은 문자열 → 숫자 (없으면 NaN)."""
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False).str.strip()
                         .replace({"-": None, "": None, "None": None, "nan": None}), errors="coerce")


def _as_list(dates):
    return [dates] if isinstance(dates, (str, date, datetime)) else list(dates)


def nxt_volume(dates, pause=0.1):
    """NXT 종목별·일별 거래량/거래대금. dates: 'YYYYMMDD' 하나 또는 목록.

    NXT 하루 총거래량 = 정규시장(regular_market) + 종가매매(closing_price) + 대량·바스켓(block_trade).
    세 화면은 서로 겹치지 않습니다(block_trade 의 isuAccTdQty 와 원 단위로 일치, 2026-02-06 삼성전자).
    거래대금은 정규시장 + 종가매매만 있습니다(대량·바스켓 화면에 거래대금이 없음).
    """
    days = [pd.Timestamp(d).strftime("%Y%m%d") for d in _as_list(dates)]
    kw = dict(dates=days, pause=pause)
    reg = nxt_fetch_range("regular_market", days[0], days[-1], **kw)
    if reg.empty:
        return pd.DataFrame()
    clo = nxt_fetch_range("closing_price", days[0], days[-1], **kw)
    blk = nxt_fetch_range("block_trade", days[0], days[-1], **kw)

    def key(df):
        return df.assign(일자=df["aggDd"].astype(str), 코드=df["isuSrdCd"].str[1:])  # 'A005930' → '005930'

    out = key(reg).rename(columns={"isuAbwdNm": "종목명", "mktNm": "시장", "accTdQty": "NXT정규량",
                                   "accTrval": "NXT정규대금", "cptrTrdPmsnCdNm": "NXT거래가능",
                                   "trdIpsbRsn": "NXT거래불가사유"})
    out = out[["일자", "코드", "종목명", "시장", "NXT정규량", "NXT정규대금", "NXT거래가능", "NXT거래불가사유"]]
    if not clo.empty:
        c = key(clo).rename(columns={"accTdQty": "NXT종가량", "accTrval": "NXT종가대금"})
        extra = set(zip(c["일자"], c["코드"])) - set(zip(out["일자"], out["코드"]))
        if extra:
            print(f"주의: 종가매매에만 있고 정규시장 목록에 없는 종목 {len(extra)}건 (합계에서 빠짐)")
        out = out.merge(c[["일자", "코드", "NXT종가량", "NXT종가대금"]], on=["일자", "코드"], how="left")
    else:
        out["NXT종가량"], out["NXT종가대금"] = 0, 0
    if not blk.empty:
        b = key(blk).assign(NXT대량량=lambda x: _num(x["bltdAccTdQty"]))
        b = b.groupby(["일자", "코드"], as_index=False)["NXT대량량"].sum()
        out = out.merge(b, on=["일자", "코드"], how="left")
    else:
        out["NXT대량량"] = 0
    for c in ("NXT정규량", "NXT정규대금", "NXT종가량", "NXT종가대금", "NXT대량량"):
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0)
    out["NXT거래량"] = out["NXT정규량"] + out["NXT종가량"] + out["NXT대량량"]
    out["NXT거래대금"] = out["NXT정규대금"] + out["NXT종가대금"]
    # 정규시장 스냅샷 적재 시각 (일자별 최댓값). 20시 이후면 애프터마켓까지 들어간 값입니다
    out.attrs["loaded_at"] = reg.groupby("aggDd")["registDt"].max().dt.strftime("%Y-%m-%d %H:%M").to_dict()
    out.attrs["empty_dates"] = reg.attrs.get("empty_dates", [])
    return out


def krx_prices(day):
    """KRX [12001] 전종목시세 하루치 (all_stock_price, JSON). 영문 코드 컬럼을 명시적으로 한글로 바꿉니다.
    거래량·거래대금은 KRX에서 체결된 것만입니다(NXT 미포함)."""
    day = pd.Timestamp(day).strftime("%Y%m%d")
    raw = krx_fetch("all_stock_price", trdDd=day)
    df = pd.DataFrame({
        "일자": day,
        "코드": raw["ISU_SRT_CD"].astype(str).str.strip(),      # 6자리 단축코드
        "KRX종목명": raw["ISU_ABBRV"].astype(str).str.strip(),
        "KRX시장": raw["MKT_NM"].astype(str).str.strip().replace({"KOSDAQ GLOBAL": "KOSDAQ"}),
        "소속부": raw["SECT_TP_NM"].astype(str).str.strip() if "SECT_TP_NM" in raw else "",
        "KRX종가": _num(raw["TDD_CLSPRC"]),
        "KRX거래량": _num(raw["ACC_TRDVOL"]),
        "KRX거래대금": _num(raw["ACC_TRDVAL"]),
        "시가총액": _num(raw["MKTCAP"]),
    })
    if df["KRX거래량"].notna().sum() == 0:  # 휴장일은 값이 전부 '-' 로 옵니다
        raise ValueError(f"{day}: KRX 거래 데이터가 없습니다(휴장일이거나 아직 집계 전).")
    return df


def krx_range(dates, pause=0.3):
    """여러 거래일의 KRX 전종목시세를 이어 붙입니다 (하루 1회 호출)."""
    days = _as_list(dates)
    parts = []
    for i, d in enumerate(days):
        parts.append(krx_prices(d))
        if pause and i < len(days) - 1:
            time.sleep(pause)
    return pd.concat(parts, ignore_index=True)


def compare(nxt, krx):
    """NXT·KRX를 (일자, 6자리 코드)로 outer join 하고 비중을 계산합니다.

    거래소: 'NXT·KRX' (둘 다 있음) / 'KRX만' (NXT 거래 대상이 아닌 종목) / 'NXT만' (KRX 목록에 없음 — 보통 0건)
    NXT점유율(%)  = NXT / (NXT + KRX) × 100   ← 두 거래소 합계 중 NXT 몫 (0~100)
    NXT/KRX(%)   = NXT / KRX × 100           ← 원본 앱의 '비중'. KRX보다 많으면 100을 넘습니다
    """
    df = krx.merge(nxt, on=["일자", "코드"], how="outer", indicator=True)
    df["거래소"] = df["_merge"].map({"both": "NXT·KRX", "left_only": "KRX만", "right_only": "NXT만"})
    df["종목명"] = df["종목명"].fillna(df["KRX종목명"]) if "종목명" in df else df["KRX종목명"]
    df["시장"] = df["KRX시장"].fillna(df.get("시장"))
    df["NXT종목"] = df["거래소"] != "KRX만"
    for c in ("NXT거래량", "NXT거래대금", "KRX거래량", "KRX거래대금"):
        df[c] = df[c].fillna(0)
    df["합계거래량"] = df["NXT거래량"] + df["KRX거래량"]
    df["합계거래대금"] = df["NXT거래대금"] + df["KRX거래대금"]
    df["NXT점유율(%)"] = (df["NXT거래량"] / df["합계거래량"].replace(0, np.nan) * 100).round(2)
    df["NXT대금점유율(%)"] = (df["NXT거래대금"] / df["합계거래대금"].replace(0, np.nan) * 100).round(2)
    df["NXT/KRX(%)"] = (df["NXT거래량"] / df["KRX거래량"].replace(0, np.nan) * 100).round(2)
    return df.drop(columns=["_merge", "KRX종목명", "KRX시장"]).reset_index(drop=True)


def share_summary(df, by=("시장",)):
    """그룹별 합계와 비중. 두 모집단을 나란히 보여 줍니다.
    - 'NXT 거래종목': NXT에서 거래된 종목만 (NXT 종목 vs 같은 종목의 KRX 거래)
    - '시장 전체'   : KOSPI·KOSDAQ 전 종목 (NXT 미거래 종목의 KRX 거래까지 분모에 포함)"""
    by = list(by)
    d = df[df["시장"].isin(MARKETS)]
    rows = []
    for universe, sub in (("NXT 거래종목", d[d["NXT종목"]]), ("시장 전체", d)):
        groups = list(sub.groupby(by))
        # 마지막 기준(보통 '시장')을 합친 '합계' 행도 붙입니다
        if len(by) == 1:
            groups.append((("합계",), sub))
        else:
            groups += [((*(k if isinstance(k, tuple) else (k,)), "합계"), g) for k, g in sub.groupby(by[:-1])]
        for keys, g in groups:
            keys = keys if isinstance(keys, tuple) else (keys,)
            n, k, nv, kv = g["NXT거래량"].sum(), g["KRX거래량"].sum(), g["NXT거래대금"].sum(), g["KRX거래대금"].sum()
            rows.append({"모집단": universe, **dict(zip(by, keys)), "종목수": int(len(g)),
                         "NXT거래량": n, "KRX거래량": k,
                         "NXT점유율(%)": round(n / (n + k) * 100, 2) if n + k else np.nan,
                         "NXT/KRX(%)": round(n / k * 100, 2) if k else np.nan,
                         "NXT거래대금": nv, "KRX거래대금": kv,
                         "NXT대금점유율(%)": round(nv / (nv + kv) * 100, 2) if nv + kv else np.nan})
    return pd.DataFrame(rows)


def krw(v, digits=1):
    """원 → '138.0조' / '5,027억'."""
    if v is None or pd.isna(v):
        return "-"
    a = abs(v)
    if a >= 1e12:
        return f"{v / 1e12:.{digits}f}조"
    if a >= 1e8:
        return f"{v / 1e8:,.0f}억"
    if a >= 1e4:
        return f"{v / 1e4:,.0f}만"
    return f"{v:,.0f}"


def shares(v):
    """주 → '1.2억주' / '3,456만주'."""
    if v is None or pd.isna(v):
        return "-"
    return f"{v / 1e8:.2f}억주" if abs(v) >= 1e8 else f"{v / 1e4:,.0f}만주"


# 차트 색 (시장은 고정 순서: KOSPI 1번, KOSDAQ 2번 / 거래소는 NXT 강조색, KRX 중립 회색)
MKT_COLOR = {"KOSPI": "#2a78d6", "KOSDAQ": "#eb6834"}
NXT_COLOR, KRX_COLOR = "#6250d6", "#c3c2b7"

# 한글 차트 폰트
import matplotlib.pyplot as plt
try:
    import koreanize_matplotlib  # noqa: F401  (Colab: 위 셀에서 설치)
except ImportError:
    if sys.platform.startswith("win"):
        plt.rcParams["font.family"] = "Malgun Gothic"
    elif sys.platform == "darwin":
        plt.rcParams["font.family"] = "AppleGothic"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False

print("NXT·KRX 준비 완료", "(Colab)" if IN_COLAB else "(로컬)",
      "| KRX 계정:", "설정됨" if os.environ.get("KRX_ID") and os.environ.get("KRX_PW") else "없음 — KRX 호출이 거절됩니다")
