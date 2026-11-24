# %% [markdown]
# # 1-01 일별 NXT vs KRX 거래량 비중 — 종목별·시장별로 NXT가 얼마나 가져갔나
#
# **질문 예시:** "어제 넥스트레이드 거래량이 KRX 대비 얼마나 됐어?", "NXT 비중이 제일 높은 종목은?", "코스닥이 코스피보다 NXT 비중이 높아?"
#
# 원본은 `krxnewsscrap`의 `krxnxtplotly.py`(Streamlit)·`krxvsnxt.ipynb`입니다. 그 아이디어를 패키지 호출로 다시 짜고,
# 무엇과 무엇을 비교하는지 분명히 했습니다.
#
# | 항목 | 출처 |
# |---|---|
# | NXT 거래량·거래대금 | `nxt_data_api` — `regular_market` + `closing_price` + `block_trade` (세 화면 합계) |
# | KRX 거래량·거래대금·시가총액 | `krx_data_api` `all_stock_price` ([12001] 전종목시세, JSON) |
# | 조인 키 | 6자리 단축코드 (NXT `isuSrdCd`의 앞 `A` 제거 = KRX `ISU_SRT_CD`) |
#
# **두 거래소의 숫자는 서로 배타적입니다.** KRX 거래량은 KRX에서 체결된 것만, NXT 거래량은 NXT에서 체결된 것만 담습니다
# (`docs/NXT_거래현황_API_정리.md` §2.1). 그래서 "전체 거래량"은 둘을 더한 값입니다.

# %%
DAY = "20261124"        # 조회일 (매매거래일, YYYYMMDD)
MIN_VALUE = 100e8       # 종목 순위에 넣을 최소 합계 거래대금 (원). 거래가 거의 없는 종목의 극단값을 거릅니다
TOP_N = 20

# %% [markdown]
# ## 1. 데이터 받기
# NXT의 하루 거래는 화면 세 개로 나뉘어 있습니다. 서로 겹치지 않아서 **셋을 더해야 NXT 총거래량**이 됩니다.
#
# | 화면 | 패키지 이름 | 담긴 거래 |
# |---|---|---|
# | 거래현황 > 정규시장 | `regular_market` | NXT 연속매매 체결분. 20:05에 집계된 스냅샷이라 애프터마켓(~20:00)까지 들어 있습니다 |
# | 거래현황 > 종가매매 | `closing_price` | KRX 종가로 체결되는 종가매매 세션 (체결된 종목만 나옴) |
# | 거래현황 > 대량·바스켓매매 | `block_trade` | 대량·바스켓매매 (있는 날만, 대개 0건). **거래대금 필드가 없습니다** |
#
# KRX 쪽은 [12001] 전종목시세의 `ACC_TRDVOL`(거래량)·`ACC_TRDVAL`(거래대금)입니다.
# 2026-07-02부터 `all_stock_price`는 영문 코드 컬럼(`ISU_SRT_CD`, `ACC_TRDVOL` …)으로 오므로 헬퍼 `krx_prices()`가 컬럼을 하나씩 짝지어 바꿉니다.

# %%
nxt = nxt_volume(DAY)
krx = krx_prices(DAY)
print(f"NXT {len(nxt)}종목 (정규시장 적재 시각 {nxt.attrs['loaded_at'].get(DAY)}), KRX {len(krx)}종목")

session = pd.DataFrame({
    "거래량": [nxt["NXT정규량"].sum(), nxt["NXT종가량"].sum(), nxt["NXT대량량"].sum()],
    "거래대금": [nxt["NXT정규대금"].sum(), nxt["NXT종가대금"].sum(), np.nan],
}, index=["정규시장", "종가매매", "대량·바스켓"])
session["거래량 비중(%)"] = (session["거래량"] / session["거래량"].sum() * 100).round(3)
session.assign(거래량=session["거래량"].map(lambda v: f"{v:,.0f}주"), 거래대금=session["거래대금"].map(krw))

# %% [markdown]
# ## 2. 6자리 코드로 맞추기
# KRX 전종목(코스피·코스닥·코넥스, 우선주 포함)과 NXT 거래종목을 outer join 합니다.
# - **NXT·KRX**: 두 곳에서 모두 거래된 종목
# - **KRX만**: NXT 거래 대상이 아닌 종목 (코넥스 전부, 대부분의 중소형주·우선주). NXT 거래량은 0으로 둡니다
# - **NXT만**: KRX 목록에 없는 NXT 종목 — 정상이면 0건이어야 합니다

# %%
df = compare(nxt, krx)
print(df["거래소"].value_counts().to_string())
pd.crosstab(df["시장"], df["거래소"], margins=True, margins_name="합계")

# %% [markdown]
# ## 3. 시장별 요약 — 비중을 두 가지로 정의합니다
# - **NXT점유율 = NXT ÷ (NXT + KRX)**: 두 거래소 합계 중 NXT 몫. 0~100%이며 이 노트북의 기본 지표입니다.
# - **NXT/KRX = NXT ÷ KRX**: 원본 앱의 "비중(NXT/KRX)". KRX 대비 몇 %인지라서 100%를 넘을 수 있습니다.
#   (점유율 p 와는 `NXT/KRX = p / (100 − p) × 100` 관계)
#
# 모집단도 둘로 나눕니다. **NXT 거래종목**은 NXT에서 거래되는 종목끼리만 비교한 값(원본 앱과 같은 기준)이고,
# **시장 전체**는 NXT에서 거래되지 않는 종목의 KRX 거래까지 분모에 넣은 값(코넥스 제외)입니다.

# %%
summ = share_summary(df)
show = summ.copy()
for c in ("NXT거래량", "KRX거래량"):
    show[c] = show[c].map(shares)
for c in ("NXT거래대금", "KRX거래대금"):
    show[c] = show[c].map(krw)
show

# %%
fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), sharey=True)
for ax, uni in zip(axes, ["NXT 거래종목", "시장 전체"]):
    s = summ[(summ["모집단"] == uni) & summ["시장"].isin(MARKETS)].set_index("시장").loc[MARKETS]
    x = np.arange(2)
    ax.bar(x - 0.2, s["NXT점유율(%)"], 0.38, color=[MKT_COLOR[m] for m in MARKETS], label="거래량 기준")
    ax.bar(x + 0.2, s["NXT대금점유율(%)"], 0.38, color=[MKT_COLOR[m] for m in MARKETS], alpha=0.45,
           hatch="//", edgecolor="white", label="거래대금 기준")
    for i, (a, b) in enumerate(zip(s["NXT점유율(%)"], s["NXT대금점유율(%)"])):
        ax.text(i - 0.2, a + 0.8, f"{a:.1f}%", ha="center", fontsize=9)
        ax.text(i + 0.2, b + 0.8, f"{b:.1f}%", ha="center", fontsize=9)
    ax.set_xticks(x, MARKETS); ax.set_title(f"{uni}"); ax.grid(axis="y", alpha=.3)
axes[0].set_ylabel("NXT점유율 = NXT ÷ (NXT+KRX), %")
axes[0].legend(loc="upper left", fontsize=8, frameon=False)
fig.suptitle(f"{DAY} 시장별 NXT 점유율 (진한 막대: 거래량, 빗금: 거래대금)", y=1.02)
plt.show()

# %% [markdown]
# ## 4. 종목별 순위
# 합계 거래대금이 `MIN_VALUE`(기본 100억 원) 이상인 NXT 거래종목만 순위에 넣습니다.
# 거래가 거의 없는 종목은 몇 주만 체결돼도 점유율이 극단으로 튀기 때문입니다.

# %%
both = df[df["NXT종목"]].copy()
liquid = both[both["합계거래대금"] >= MIN_VALUE]
cols = ["코드", "종목명", "시장", "NXT거래량", "KRX거래량", "NXT점유율(%)", "NXT/KRX(%)", "NXT거래대금", "합계거래대금"]

def fmt(t):
    t = t[cols].copy()
    for c in ("NXT거래량", "KRX거래량"):
        t[c] = t[c].map(lambda v: f"{v:,.0f}")
    for c in ("NXT거래대금", "합계거래대금"):
        t[c] = t[c].map(krw)
    return t.reset_index(drop=True)

print(f"순위 대상 {len(liquid)} / NXT 거래종목 {len(both)}")
print(f"▶ NXT점유율 상위 {TOP_N}")
fmt(liquid.sort_values("NXT점유율(%)", ascending=False).head(TOP_N))

# %%
print(f"▶ NXT 거래대금 상위 {TOP_N}")
fmt(liquid.sort_values("NXT거래대금", ascending=False).head(TOP_N))

# %%
top = liquid.sort_values("NXT점유율(%)", ascending=False).head(30).iloc[::-1]
all_share = summ.query("모집단 == 'NXT 거래종목' and 시장 == '합계'")["NXT점유율(%)"].iloc[0]
fig, ax = plt.subplots(figsize=(8, 9))
ax.barh(top["종목명"], top["NXT점유율(%)"], color=[MKT_COLOR[m] for m in top["시장"]], height=0.7)
ax.axvline(all_share, color="#52514e", ls="--", lw=1)
ax.text(all_share, len(top) - 0.3, f" NXT 거래종목 전체 {all_share:.1f}%", fontsize=9, color="#52514e", va="bottom")
for y, v in enumerate(top["NXT점유율(%)"]):
    ax.text(v + 0.5, y, f"{v:.1f}", va="center", fontsize=8)
ax.set_xlabel("NXT점유율 = NXT ÷ (NXT+KRX) 거래량, %"); ax.grid(axis="x", alpha=.3)
ax.set_title(f"{DAY} NXT점유율 상위 30종목 (합계 거래대금 {krw(MIN_VALUE)} 이상)")
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=MKT_COLOR[m], label=m) for m in MARKETS], loc="lower right", frameon=False)
plt.show()

# %% [markdown]
# ## 5. 분포 — 대부분의 종목은 어디쯤인가
# 종목별 NXT점유율 분포입니다. 시장 합계 점유율은 거래가 많은 대형주가 끌고 가므로, 전형적인 종목은 중앙값으로 봅니다.

# %%
fig, ax = plt.subplots(figsize=(9, 3.6))
bins = np.arange(0, 101, 5)
for m in MARKETS:
    v = both.loc[both["시장"] == m, "NXT점유율(%)"].dropna()
    ax.hist(v, bins=bins, histtype="step", lw=2, color=MKT_COLOR[m], label=f"{m} (n={len(v)}, 중앙값 {v.median():.1f}%)")
    ax.axvline(v.median(), color=MKT_COLOR[m], ls=":", lw=1.5)
ax.set_xlabel("종목별 NXT점유율 (거래량, %)"); ax.set_ylabel("종목 수"); ax.grid(axis="y", alpha=.3)
ax.legend(frameon=False); ax.set_title(f"{DAY} NXT 거래종목의 점유율 분포")
plt.show()

over = both[both["NXT/KRX(%)"] > 100]
print(f"NXT 거래량이 KRX보다 많은 종목(NXT/KRX > 100%): {len(over)}개 / {len(both)}개")

# %% [markdown]
# ## 6. 확인할 것 — 거래가 없거나 한쪽에서 막힌 종목
# NXT `거래가능 = 거래불가`(투자경고·위험, 거래정지 등)인 종목과, 어느 한쪽 거래량이 0인 종목입니다.
# 이런 종목은 점유율이 0% 또는 100% 근처로 나오므로 해석에서 빼는 편이 낫습니다.

# %%
odd = both[(both["NXT거래가능"] != "전체") | (both["NXT거래량"] == 0) | (both["KRX거래량"] == 0)]
odd[["코드", "종목명", "시장", "NXT거래가능", "NXT거래불가사유", "NXT거래량", "KRX거래량", "NXT점유율(%)"]].reset_index(drop=True)

# %% [markdown]
# ## 결과 읽는 법과 한계
# - **"NXT 거래종목" 기준 점유율**이 원본 앱의 숫자(NXT/KRX)를 점유율로 바꾼 것입니다. 언론 보도의 "NXT 비중"은 보통 이 모집단입니다.
#   "시장 전체" 기준은 NXT가 거래하지 않는 종목의 KRX 거래까지 분모에 넣어서 훨씬 낮습니다. 코스닥은 NXT 비대상 소형주 거래가 많아 차이가 큽니다.
# - **거래량 기준과 거래대금 기준이 다릅니다.** NXT 거래종목은 대체로 대형·고가주라서, 시장 전체 기준으로는 거래대금 점유율이 거래량 점유율보다 높게 나옵니다.
# - NXT 거래량은 애프터마켓(~20:00)까지 포함합니다(정규시장 스냅샷이 20:05 집계). 프리마켓(08:00~)도 같은 화면에 들어가는 것으로 보이지만
#   세션별로 쪼개 확인하지는 않았습니다. KRX도 장 시작 전·마감 후 시간외 거래가 있어 "같은 시간대"끼리의 비교는 아닙니다.
#   (KRX [12001] 거래량에 시간외·대량매매가 어디까지 들어가는지도 이 노트북에서 따로 확인하지 않았습니다.)
# - NXT 거래대금에는 대량·바스켓매매 대금이 빠져 있습니다(화면에 거래대금 필드가 없음). 대량매매는 드물어(2026-08-03~11-24 조회 결과 0건) 영향은 작습니다.
# - `closing_price`(종가매매)는 체결된 종목만 나오므로, 목록에 없는 종목의 종가매매 거래량은 0으로 둡니다.
# - KRX `all_stock_price`는 휴장일을 넣으면 값이 전부 `-`로 옵니다(2026-11-22 확인). 헬퍼는 이때 오류를 냅니다. NXT는 휴장일에 0건입니다.
