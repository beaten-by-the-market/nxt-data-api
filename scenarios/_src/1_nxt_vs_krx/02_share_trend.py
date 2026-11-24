# %% [markdown]
# # 1-02 NXT 점유율 추이 — 일별·종목별 기간 합계와 개장 이후 월별 흐름
#
# **질문 예시:** "최근 석 달 넥스트레이드 비중이 늘었어?", "이번 분기 NXT에서 많이 거래된 종목은?", "NXT 개장 이후 점유율이 어떻게 변했어?"
#
# 원본은 `krxnewsscrap`의 `krxvsnxt_cumul.ipynb`입니다(개장일부터 입력일까지 매일 NXT·KRX를 받아 날짜별·종목별로 합산).
# 여기서는 같은 계산을 두 단계로 나눴습니다. 최근 구간은 **매일**, 개장 이후 전체는 **월말 거래일 하루씩** 받아 호출 수를 줄입니다.
#
# | 항목 | 출처 |
# |---|---|
# | 매매거래일 목록 | `krx_data_api.daily_snapshots.trading_days` (삼성전자 [12003] 시세추이의 일자) |
# | NXT 거래량·거래대금 | `nxt_data_api.fetch_range` — `regular_market` + `closing_price` + `block_trade` |
# | KRX 거래량·거래대금 | `krx_data_api` `all_stock_price` ([12001] 전종목시세, 하루 1회 호출) |
#
# 비중의 정의와 모집단 구분(NXT 거래종목 / 시장 전체)은 [1-01](01_daily_share.ipynb)과 같습니다.
# **NXT점유율 = NXT ÷ (NXT + KRX)**, NXT/KRX는 원본의 "비중"입니다.

# %%
END = "20261124"          # 마지막 매매거래일
DAILY_START = "20260901"  # 매일 받는 구간의 시작
LAUNCH = "20250304"       # NXT 개장일 (시범 10종목)
MIN_VALUE = 1000e8        # 종목 순위에 넣을 최소 기간 합계 거래대금 (원)
TOP_N = 20

# %% [markdown]
# ## 1. 매매거래일
# NXT는 휴장일에 0건, KRX `all_stock_price`는 휴장일에 값이 전부 `-`로 옵니다. 달력일을 돌지 않고 KRX 매매거래일 목록을 먼저 받습니다.

# %%
cal = trading_days(LAUNCH, END)
days = [d for d in cal if d >= DAILY_START]
months = pd.Series(cal, index=pd.to_datetime(cal)).groupby(lambda t: t.strftime("%Y-%m")).last().tolist()
print(f"개장 이후 매매거래일 {len(cal)}일 ({cal[0]} ~ {cal[-1]})")
print(f"일별 구간 {len(days)}일 ({days[0]} ~ {days[-1]}), 월말 표본 {len(months)}일")

# %% [markdown]
# ## 2. 일별 추이 (최근 구간)
# 하루에 NXT 3회 + KRX 1회를 호출합니다. 60거래일이면 2~4분쯤 걸립니다.

# %%
t0 = time.time()
nxt = nxt_volume(days)
krx = krx_range(days)
df = compare(nxt, krx)
missing = sorted(set(days) - set(nxt["일자"]))
print(f"{time.time() - t0:.0f}초, {len(df):,}행. NXT 데이터가 없던 KRX 거래일: {missing or '없음'}")

daily = share_summary(df, by=("일자", "시장"))
daily["일자"] = pd.to_datetime(daily["일자"])

def pick(universe, market, col):
    return daily[(daily["모집단"] == universe) & (daily["시장"] == market)].set_index("일자")[col]

tbl = pd.DataFrame({
    "NXT 종목수": pick("NXT 거래종목", "합계", "종목수"),
    "점유율·NXT종목·거래량": pick("NXT 거래종목", "합계", "NXT점유율(%)"),
    "점유율·NXT종목·대금": pick("NXT 거래종목", "합계", "NXT대금점유율(%)"),
    "점유율·시장전체·대금": pick("시장 전체", "합계", "NXT대금점유율(%)"),
    "NXT 거래대금": pick("시장 전체", "합계", "NXT거래대금").map(krw),
    "KRX 거래대금": pick("시장 전체", "합계", "KRX거래대금").map(krw),
})
tbl.index = tbl.index.strftime("%Y-%m-%d")
print("(점유율 단위 %) 처음 5일과 마지막 5일")
pd.concat([tbl.head(5), tbl.tail(5)])

# %%
fig, axes = plt.subplots(1, 2, figsize=(13, 4), sharey=True)
panels = [("NXT 거래종목", "NXT점유율(%)", "NXT 거래종목 기준 · 거래량"),
          ("시장 전체", "NXT대금점유율(%)", "시장 전체 기준 · 거래대금")]
for ax, (uni, col, title) in zip(axes, panels):
    for m in MARKETS:
        s = pick(uni, m, col)
        ax.plot(s.index, s.values, color=MKT_COLOR[m], lw=2, label=m)
        ax.annotate(f"{s.iloc[-1]:.1f}", (s.index[-1], s.iloc[-1]), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=9)
    s = pick(uni, "합계", col)
    ax.plot(s.index, s.values, color="#52514e", lw=1.5, ls="--", label="합계")
    ax.set_title(title); ax.grid(alpha=.3); ax.tick_params(axis="x", rotation=30)
axes[0].set_ylabel("NXT점유율 = NXT ÷ (NXT+KRX), %")
axes[0].legend(frameon=False)
fig.suptitle(f"일별 NXT 점유율 ({days[0]} ~ {days[-1]})", y=1.02)
plt.show()

# %%
s_n = pick("시장 전체", "합계", "NXT거래대금") / 1e12
s_k = pick("시장 전체", "합계", "KRX거래대금") / 1e12
fig, ax = plt.subplots(figsize=(13, 4))
ax.bar(s_k.index, s_k.values, color=KRX_COLOR, label="KRX", width=0.8)
ax.bar(s_n.index, s_n.values, bottom=s_k.values, color=NXT_COLOR, label="NXT", width=0.8)
ax.set_ylabel("거래대금 (조원)"); ax.grid(axis="y", alpha=.3); ax.legend(frameon=False, loc="upper left")
ax.set_title("코스피+코스닥 일별 거래대금 — KRX와 NXT를 쌓은 값 (두 거래소 합계 = 전체 시장)")
plt.show()

# %% [markdown]
# ## 3. 종목별 기간 합계
# 구간 거래량·거래대금을 종목별로 더한 뒤 점유율을 다시 계산합니다(일별 점유율의 평균이 아닙니다).
# NXT 거래 대상 종목은 주기적으로 바뀝니다. 그래서 **그 종목이 NXT 목록에 있던 날만** 더합니다.
# NXT에 없던 날의 KRX 거래까지 분모에 넣으면 점유율이 낮게 나오기 때문입니다. `NXT거래일수`가 그 날 수입니다.

# %%
sub = df[df["NXT종목"]]                     # 그 종목이 NXT 목록에 있던 날만
nxt_codes = set(sub["코드"])
by_stock = sub.groupby("코드").agg(
    종목명=("종목명", "last"), 시장=("시장", "last"), NXT거래일수=("NXT종목", "sum"),
    NXT거래량=("NXT거래량", "sum"), KRX거래량=("KRX거래량", "sum"),
    NXT거래대금=("NXT거래대금", "sum"), KRX거래대금=("KRX거래대금", "sum"))
by_stock["합계거래대금"] = by_stock["NXT거래대금"] + by_stock["KRX거래대금"]
by_stock["NXT점유율(%)"] = (by_stock["NXT거래량"] / (by_stock["NXT거래량"] + by_stock["KRX거래량"]) * 100).round(2)
by_stock["NXT대금점유율(%)"] = (by_stock["NXT거래대금"] / by_stock["합계거래대금"] * 100).round(2)
by_stock["NXT/KRX(%)"] = (by_stock["NXT거래량"] / by_stock["KRX거래량"].replace(0, np.nan) * 100).round(2)

first, last = set(nxt.loc[nxt["일자"] == days[0], "코드"]), set(nxt.loc[nxt["일자"] == days[-1], "코드"])
print(f"구간 중 한 번이라도 NXT에서 거래된 종목 {len(nxt_codes)}개 (첫날 {len(first)}, 마지막 날 {len(last)})")
print(f"  첫날 목록에 없다가 추가: {len(last - first)}개 / 첫날 있다가 빠짐: {len(first - last)}개")

def fmt(t):
    t = t.reset_index()[["코드", "종목명", "시장", "NXT거래일수", "NXT점유율(%)", "NXT대금점유율(%)", "NXT/KRX(%)",
                         "NXT거래대금", "합계거래대금"]].copy()
    for c in ("NXT거래대금", "합계거래대금"):
        t[c] = t[c].map(krw)
    return t

liquid = by_stock[by_stock["합계거래대금"] >= MIN_VALUE]
print(f"\n▶ 기간 NXT점유율 상위 {TOP_N} (기간 합계 거래대금 {krw(MIN_VALUE)} 이상 {len(liquid)}개 중)")
fmt(liquid.sort_values("NXT점유율(%)", ascending=False).head(TOP_N))

# %%
print(f"▶ 기간 NXT 거래대금 상위 {TOP_N}")
fmt(by_stock.sort_values("NXT거래대금", ascending=False).head(TOP_N))

# %% [markdown]
# ## 4. 개장 이후 월별 흐름 (월말 거래일 하루씩)
# 매월 마지막 매매거래일 하루치만 받아 NXT 거래 종목 수와 점유율이 어떻게 늘었는지 봅니다.
# 하루 표본이라 그날의 장세에 따라 들쭉날쭉할 수 있습니다. 매일 값이 필요하면 2장의 `DAILY_START`를 앞당기세요(호출 수가 늘어납니다).

# %%
t0 = time.time()
mdf = compare(nxt_volume(months), krx_range(months))
monthly = share_summary(mdf, by=("일자", "시장"))
monthly["일자"] = pd.to_datetime(monthly["일자"])
print(f"{time.time() - t0:.0f}초")

def mpick(universe, market, col):
    return monthly[(monthly["모집단"] == universe) & (monthly["시장"] == market)].set_index("일자")[col]

mt = pd.DataFrame({
    "NXT 종목수": mpick("NXT 거래종목", "합계", "종목수"),
    "KOSPI 종목": mpick("NXT 거래종목", "KOSPI", "종목수"),
    "KOSDAQ 종목": mpick("NXT 거래종목", "KOSDAQ", "종목수"),
    "점유율·NXT종목·거래량": mpick("NXT 거래종목", "합계", "NXT점유율(%)"),
    "NXT/KRX·NXT종목·거래량": mpick("NXT 거래종목", "합계", "NXT/KRX(%)"),
    "점유율·시장전체·대금": mpick("시장 전체", "합계", "NXT대금점유율(%)"),
}).fillna(0)
mt.index = mt.index.strftime("%Y-%m-%d")
mt

# %%
fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, gridspec_kw={"height_ratios": [1, 1.4]})
x = mpick("NXT 거래종목", "합계", "종목수").index
k_n = mpick("NXT 거래종목", "KOSPI", "종목수").reindex(x).fillna(0)
q_n = mpick("NXT 거래종목", "KOSDAQ", "종목수").reindex(x).fillna(0)
axes[0].bar(x, k_n, width=20, color=MKT_COLOR["KOSPI"], label="KOSPI")
axes[0].bar(x, q_n, width=20, bottom=k_n, color=MKT_COLOR["KOSDAQ"], label="KOSDAQ")
axes[0].set_ylabel("NXT 거래 종목 수"); axes[0].legend(frameon=False, loc="upper left"); axes[0].grid(axis="y", alpha=.3)
axes[0].set_title("월말 거래일 기준 NXT 거래 종목 수와 점유율")
for uni, col, ls, lab in [("NXT 거래종목", "NXT점유율(%)", "-", "NXT 거래종목 · 거래량"),
                          ("시장 전체", "NXT대금점유율(%)", "--", "시장 전체 · 거래대금")]:
    for m in MARKETS:
        s = mpick(uni, m, col)
        axes[1].plot(s.index, s.values, color=MKT_COLOR[m], ls=ls, lw=2, marker="o", ms=4, label=f"{m} · {lab}")
axes[1].set_ylabel("NXT점유율, %"); axes[1].grid(alpha=.3); axes[1].legend(frameon=False, fontsize=9, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.1))
plt.show()

# %% [markdown]
# ## 결과 읽는 법과 한계
# - **NXT 거래종목 기준**은 "NXT가 거래하는 종목에서 NXT가 얼마나 가져가나", **시장 전체 기준**은 "코스피·코스닥 전체 거래에서 NXT 몫"입니다.
#   종목 수가 늘어나는 시기에는 두 번째가 오르는데 첫 번째는 그대로일 수 있습니다.
# - 종목별 기간 점유율은 기간 합계로 다시 계산한 값이고, 그 종목이 NXT 목록에 있던 날만 셉니다.
#   `NXT거래일수`가 구간 거래일수보다 적은 종목은 구간 중에 NXT에 들어왔거나 빠진 종목입니다.
# - 일별·월별 "시장 전체" 점유율은 그날 NXT에 없던 종목의 KRX 거래도 분모에 넣습니다. 이것이 "시장 전체에서 NXT 몫"의 정의입니다.
# - NXT 거래량은 애프터마켓(~20:00)까지 포함하고, NXT 거래대금에는 대량·바스켓 대금이 없습니다(1-01 참고).
# - 월말 하루 표본은 추세를 보기 위한 것입니다. 정확한 월평균이 필요하면 그달의 모든 거래일을 받아 합산하세요.
