"""Draw every figure in the README, in a light and a dark version.

Inputs stay private and live outside the repo ($SIG_DATA, default ~/sigbot_data/writeup):
  fills_pnl.json, events_agg.json   the bot's fill log, 10-minute and 1-minute account summaries
  day1_tape.json, day1_bot.json     SIG's whole day-one trade tape against fair, and our day-one fills
  story_co03.json                   CO-03's fair values and SIG prices on election night
  leaderboard_nov9.json             all 1,969 ranked accounts
  series.npz, night.npz, results.json   from prep_data.py

The numbers quoted in the README are printed at the end and saved to $SIG_DATA/numbers.json.
"""
import datetime as dt
import json
import os
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

DATA = Path(os.environ.get("SIG_DATA", "~/sigbot_data/writeup")).expanduser()
FIG = Path(__file__).resolve().parent / "figures"
UTC = dt.timezone.utc
FALL_BACK = dt.datetime(2026, 11, 1, 6, tzinfo=UTC)          # US clocks went back an hour
NUM = {}                                                       # numbers quoted in the README

THEMES = {
    "light": dict(bg="#ffffff", ink="#1f2328", muted="#59636e", grid="#e6eaef", axis="#c4ccd4", gray="#b4bcc5",
                  s=["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]),
    "dark": dict(bg="#0d1117", ink="#e6edf3", muted="#9198a1", grid="#21262d", axis="#3d444d", gray="#4d5560",
                 s=["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"]),
}


def et(t):
    """Aware UTC datetime -> naive US Eastern."""
    return (t - dt.timedelta(hours=4 if t < FALL_BACK else 5)).replace(tzinfo=None)


def utc(s):
    return dt.datetime.fromisoformat(s[:19]).replace(tzinfo=UTC)


def load(name):
    return json.load(open(DATA / name))


def style(T):
    plt.rcParams.update({
        "font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"], "font.size": 10.5,
        "axes.unicode_minus": False,
        "figure.facecolor": T["bg"], "axes.facecolor": T["bg"], "savefig.facecolor": T["bg"],
        "text.color": T["ink"], "axes.labelcolor": T["muted"], "xtick.color": T["muted"], "ytick.color": T["muted"],
        "axes.edgecolor": T["axis"], "axes.grid": True, "grid.color": T["grid"], "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 12.5, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "axes.titlepad": 24, "legend.frameon": False, "legend.fontsize": 9.5,
        "xtick.major.size": 0, "ytick.major.size": 0, "lines.solid_capstyle": "round",
    })


def save(fig, name, theme):
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / f"{name}-{theme}.png", dpi=150, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def subtitle(ax, text, T):
    ax.text(0, 1.012, text, transform=ax.transAxes, color=T["muted"], fontsize=9.5, va="bottom")


def kfmt(ax, axis="y", unit="k"):
    f = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}{unit}")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(f)


def label(name):
    """'house:CO-03/R' -> 'CO-03 R', 'senate:RI/D' -> 'RI Senate D', 'chamber:senate/D' -> 'Senate control D'."""
    kind, rest = name.split(":")
    place, party = rest.split("/")
    if kind == "house":
        return f"{place} {party}"
    if kind == "chamber":
        return f"{place.title()} control {party}"
    return f"{place} {'Gov' if kind == 'governor' else 'Senate'} {party}"


GROUP = {"take": "Takes", "event": "Event sweeps", "quote": "Quotes", "quote?": "Quotes", "unknown": "Quotes",
         "?": "Quotes", "exit_quote": "Exits at fair", "swap_exit": "Paid exits", "event_exit": "Paid exits",
         "cash_raise": "Paid exits", "park": "Parking"}
ORDER = ["Takes", "Event sweeps", "Quotes", "Exits at fair", "Parking", "Paid exits"]

# ---------------------------------------------------------------------------------------------- data
fp, ev = load("fills_pnl.json"), load("events_agg.json")
d1, b1 = load("day1_tape.json"), load("day1_bot.json")
co, lb = load("story_co03.json"), load("leaderboard_nov9.json")
S, NI = np.load(DATA / "series.npz"), np.load(DATA / "night.npz")
RES = load("results.json")
names = list(S["names"])
idx = {n: i for i, n in enumerate(names)}
T0 = dt.datetime(2026, 10, 1, tzinfo=UTC)
y = np.array([np.nan if RES["results"][e]["y"] is None else RES["results"][e]["y"] for e in S["ids"]])
NUM["results_known"] = int(np.isfinite(y).sum())


def sig_mid(bid, ask, max_spread=0.2):
    mid = (bid + ask) / 2
    return np.where((ask - bid) <= max_spread, mid, np.nan)


fair, kal, pol = S["fair"], S["kalshi"], S["poly"]
smid = sig_mid(S["sig_bid"], S["sig_ask"])
minute_t = [T0 + dt.timedelta(minutes=m) for m in range(fair.shape[1])]


# ------------------------------------------------------------------------------------ 1 equity curve
def fig_equity(T, theme):
    rows = [r for r in ev["summary10m"] if r[1] == "LIVE" and "2026-10-01T16:00" <= r[0] <= "2026-11-04T13:10"]
    t = [et(utc(r[0])) for r in rows]
    cash = np.array([r[2] for r in rows]) / 1e3
    eq = np.array([r[3] for r in rows]) / 1e3
    fig, (a, b) = plt.subplots(2, 1, figsize=(11, 6.2), sharex=True, gridspec_kw={"height_ratios": [3.2, 1], "hspace": 0.12})
    a.plot(t, eq, color=T["s"][0], lw=2)
    end = dt.datetime(2026, 11, 4, 12)
    a.plot([t[-1], end], [eq[-1], 256.7], color=T["s"][0], lw=1.2, ls=(0, (2, 2)))
    a.scatter([end], [256.7], s=46, color=T["bg"], edgecolor=T["s"][0], lw=2, zorder=5)
    a.annotate("256.7k at the results", (end, 256.7), xytext=(-8, 10), textcoords="offset points", ha="right",
               color=T["ink"], fontsize=9.5)
    notes = [("2026-10-07T16:00", "Oct 7: slowest day, 11 fills", 0, 30, "center"),
             ("2026-11-02T21:30", "Nov 2: final-days mode", -30, 40, "right"),
             ("2026-11-03T23:00", "Polls close", 12, -40, "left")]
    for ts, txt, dx, dy, ha in notes:
        x = et(utc(ts))
        j = min(range(len(t)), key=lambda i: abs((t[i] - x).total_seconds()))
        a.annotate(txt, (t[j], eq[j]), xytext=(dx, dy), textcoords="offset points", ha=ha, fontsize=9,
                   color=T["muted"], arrowprops=dict(arrowstyle="-", color=T["axis"], lw=0.8))
    a.set_ylim(90, 275)
    kfmt(a)
    a.set_title("Account value at fair, Oct 1 – Nov 4")
    subtitle(a, "Cash plus positions valued at our Kalshi/Polymarket fair, every 10 minutes (ET)", T)
    b.fill_between(t, 0, cash, color=T["s"][2], alpha=0.35, lw=0)
    b.plot(t, cash, color=T["s"][2], lw=1.2)
    b.set_ylabel("Cash")
    kfmt(b)
    b.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.TH))
    b.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d"))
    save(fig, "equity_curve", theme)
    NUM["equity_nov4_8am"] = round(float(eq[-1]), 1)


# ------------------------------------------------------------------------------------ 2 day by day
def fig_daily(T, theme):
    by = defaultdict(float)                              # P&L at the results, by Eastern day of the fill
    for ts, m, side, px, q, f0, why in fp["fills"]:
        out = fp["outcomes"].get(m)
        if out is None or out[0] is None:
            continue
        by[et(utc(ts)).date().isoformat()] += (1 if side == "bid" else -1) * (out[0] - px) * q
    days = sorted(by)
    v = np.array([by[d] for d in days]) / 1e3
    x = [dt.datetime.fromisoformat(d) for d in days]
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.bar(x, v, width=0.72, color=[T["s"][0] if a >= 0 else T["s"][1] for a in v], edgecolor=T["bg"], lw=1)
    for xi, vi, d in zip(x, v, days):
        if abs(vi) >= 12:
            ax.annotate(f"{vi:+.1f}k", (xi, vi), xytext=(0, 4 if vi > 0 else -12), textcoords="offset points",
                        ha="center", fontsize=9, color=T["ink"])
    ax.axhline(0, color=T["axis"], lw=1)
    kfmt(ax)
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.TH))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d"))
    ax.set_xlim(dt.datetime(2026, 9, 30, 12), dt.datetime(2026, 11, 4, 12))
    ax.set_title("What each day's trades were worth at the results")
    subtitle(ax, "Every logged fill valued against the race's actual outcome, grouped by the Eastern day it was made", T)
    save(fig, "daily", theme)
    NUM["last_two_days_k"] = round(float(v[-2] + v[-1]), 1)
    NUM["by_day_k"] = {d: round(float(a), 1) for d, a in zip(days, v)}
    NUM["total_fills_k"] = round(float(v.sum()), 1)


# ------------------------------------------------------------------------------------ 3 by purpose
def fig_purpose(T, theme):
    pnl, edge = defaultdict(float), defaultdict(float)
    for k, val in fp["pnl_purpose"].items():
        pnl[GROUP.get(k, "Quotes")] += val
    for k, val in fp["edge_purpose"].items():
        edge[GROUP.get(k, "Quotes")] += val
    cats = ORDER[::-1]
    yy = np.arange(len(cats))
    fig, ax = plt.subplots(figsize=(10, 4.6))
    h = 0.36
    ax.barh(yy + h / 2, [edge.get(c, np.nan) / 1e3 for c in cats], h, color=T["s"][0], edgecolor=T["bg"], lw=1.5,
            label="Edge against fair when the trade was made")
    ax.barh(yy - h / 2, [pnl[c] / 1e3 for c in cats], h, color=T["s"][3], edgecolor=T["bg"], lw=1.5,
            label="Value at the actual results")
    for i, c in enumerate(cats):
        for val, off in ((edge.get(c), h / 2), (pnl[c], -h / 2)):
            if val is None:
                continue
            ax.text(val / 1e3 + (2 if val >= 0 else -2), i + off, f"{val / 1e3:+.1f}k", va="center",
                    ha="left" if val >= 0 else "right", fontsize=9, color=T["ink"])
    ax.set_yticks(yy, cats)
    ax.axvline(0, color=T["axis"], lw=1)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(-125, 175)
    kfmt(ax, "x")
    ax.legend(loc="lower right")
    ax.set_title("Where the money came from, by type of trade")
    subtitle(ax, "11,137 logged fills. Parking was the last morning only.", T)
    save(fig, "purpose", theme)
    NUM["purpose_pnl"] = {c: round(pnl[c] / 1e3, 1) for c in ORDER}
    NUM["purpose_edge"] = {c: round(edge.get(c, 0) / 1e3, 1) for c in ORDER}


# ------------------------------------------------------------------------------------ 4 day one tape
def fig_day1(T, theme):
    pts = np.array([[p[0], p[2], p[3], p[4]] for p in d1["pts"]], dtype=float)
    noon = dt.datetime(2026, 10, 1, 12)
    tt = [noon + dt.timedelta(seconds=s) for s in pts[:, 0]]
    gap = np.clip((pts[:, 1] - pts[:, 2]) * 100, -100, 100)
    size = 4 + 7 * np.log10(np.maximum(pts[:, 3], 1))
    fig, (a, b) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1.1], "hspace": 0.12})
    near = np.abs(gap) < 2
    a.scatter(np.array(tt)[near], gap[near], s=size[near] * 0.6, color=T["gray"], alpha=0.35, lw=0, rasterized=True)
    for mask, c in ((gap >= 2, T["s"][1]), (gap <= -2, T["s"][0])):
        a.scatter(np.array(tt)[mask], gap[mask], s=size[mask], color=c, alpha=0.45, lw=0, rasterized=True)
    ours = [(noon + dt.timedelta(hours=int(f[0][:2]) - 16, minutes=int(f[0][3:5]), seconds=int(f[0][6:8])),
             (f[3] - f[5]) * 100) for f in b1["day1_fills"]]
    a.scatter([o[0] for o in ours], [o[1] for o in ours], s=16, marker="D", color=T["ink"], edgecolor=T["bg"], lw=0.6,
              zorder=4)
    a.axhline(0, color=T["axis"], lw=1)
    a.set_ylabel("Trade price minus fair (points)")
    a.set_ylim(-102, 102)
    a.legend(handles=[Line2D([], [], ls="", marker="o", color=T["s"][1], label="YES bought 2+ points above fair"),
                      Line2D([], [], ls="", marker="o", color=T["s"][0], label="YES sold 2+ points below fair"),
                      Line2D([], [], ls="", marker="o", color=T["gray"], label="Within 2 points (1 in 5 shown)"),
                      Line2D([], [], ls="", marker="D", color=T["ink"], label="Our fills")],
             loc="lower right", ncol=2)
    a.set_title("Day one: every trade on SIG against fair, Oct 1, noon – 8 pm ET")
    subtitle(a, f"{d1['summary']['trades']:,} trades. Dot size grows with trade size (log scale).", T)
    tl = d1["timeline"]
    xb = [noon + dt.timedelta(minutes=10 * i + 5) for i in tl["bin"]]
    wild = np.array(tl["wild"]) / 1e3
    rest = np.array(tl["off"]) / 1e3 - wild
    w = dt.timedelta(minutes=8.4)
    b.bar(xb, wild, w, color=T["s"][1], edgecolor=T["bg"], lw=0.8, label="25+ points off fair")
    b.bar(xb, rest, w, bottom=wild, color=T["s"][3], edgecolor=T["bg"], lw=0.8, label="2–25 points off")
    b.set_ylabel("Value off fair")
    kfmt(b)
    b.legend(loc="upper right", ncol=2)
    b.xaxis.set_major_formatter(mdates.DateFormatter("%-I %p"))
    save(fig, "day1_tape", theme)
    s = d1["summary"]
    NUM["day1"] = {"trades": s["trades"], "off_val_M": round(s["off_val"] / 1e6, 2), "wild_val_M": round(s["wild_val"] / 1e6, 2),
                   "first_hour_M": round(s["first_hour_off"] / 1e6, 2), "markets_off": s["markets_off"]}
    # how far from fair the day-one money was, and how much sat at the price limits
    off = np.abs(pts[:, 1] - pts[:, 2]) * pts[:, 3]
    g = np.abs(gap)
    bands = [(2, 10), (10, 25), (25, 50), (50, 101)]
    NUM["day1_bands_M"] = {f"{lo}-{hi}": round(float(off[(g >= lo) & (g < hi)].sum() / 1e6), 2) for lo, hi in bands}
    lim = ((pts[:, 1] <= 0.01) & (pts[:, 2] >= 0.05)) | ((pts[:, 1] >= 0.99) & (pts[:, 2] <= 0.95))
    NUM["day1_at_limits"] = {"trades": int(lim.sum()), "shares_M": round(float(pts[lim, 3].sum() / 1e6), 2),
                             "value_M": round(float(off[lim].sum() / 1e6), 2)}


# ------------------------------------------------------------------------------------ 5 CO-03
def fig_co03(T, theme):
    t0, t1 = dt.datetime(2026, 11, 3, 18), dt.datetime(2026, 11, 4, 12)
    ext = [(et(utc(r[0])), r[1]) for r in co["ext"]["895"] if r[1] is not None]
    tops = [(et(utc(r[0])), r[1], r[2]) for r in co["tops"]["895"]]
    ext = [r for r in ext if t0 <= r[0] <= t1]
    tops = [r for r in tops if t0 <= r[0] <= t1 and r[1] and r[2]]
    fills = [(et(utc(f[0])), f[2], f[3], f[4]) for f in fp["fills"] if f[1] == "house:CO-03/R"]
    fig, (a, b) = plt.subplots(2, 1, figsize=(11, 6.8), sharex=True, gridspec_kw={"height_ratios": [2.6, 1], "hspace": 0.12})
    a.fill_between([r[0] for r in tops], [r[1] for r in tops], [r[2] for r in tops], step="post", color=T["s"][0],
                   alpha=0.25, lw=0, label="SIG best bid to best ask")
    a.plot([r[0] for r in ext], [r[1] for r in ext], color=T["ink"], lw=1.4, label="Fair (Kalshi + Polymarket)")
    night = [f for f in fills if t0 <= f[0] <= t1]
    for side, mk, c, lab in (("bid", "^", T["s"][2], "We bought R"), ("ask", "v", T["s"][1], "We sold R")):
        xs = [f for f in night if f[1] == side]
        a.scatter([f[0] for f in xs], [f[2] for f in xs], s=[8 + 3 * np.sqrt(f[3]) / 3 for f in xs], marker=mk,
                  color=c, edgecolor=T["bg"], lw=0.5, alpha=0.9, zorder=4, label=lab)
    a.annotate("1:30 am: fair 0.62,\nSIG's best bid 0.475", (dt.datetime(2026, 11, 4, 1, 30), 0.55), xytext=(30, -50),
               textcoords="offset points", fontsize=9, color=T["muted"],
               arrowprops=dict(arrowstyle="-", color=T["axis"], lw=0.8))
    a.set_ylim(0, 1)
    a.set_ylabel("Price of R YES")
    a.legend(loc="lower right", ncol=2)
    a.set_title("CO-03 on election night: SIG trailed every leg")
    subtitle(a, "Colorado's 3rd district, Republican market, 6 pm Nov 3 – noon Nov 4 ET. Marker size grows with shares.", T)
    pos, cum = [], 0.0
    for f in fills:
        cum += f[3] if f[1] == "bid" else -f[3]
        pos.append((f[0], cum))
    before = [p for p in pos if p[0] < t0]
    series = ([(t0, before[-1][1])] if before else []) + [p for p in pos if t0 <= p[0] <= t1] + [(t1, pos[-1][1])]
    b.step([p[0] for p in series], [p[1] / 1e3 for p in series], where="post", color=T["s"][0], lw=1.6)
    b.axhline(0, color=T["axis"], lw=1)
    b.set_ylabel("Our R shares")
    kfmt(b)
    b.xaxis.set_major_formatter(mdates.DateFormatter("%-I %p"))
    save(fig, "co03", theme)
    NUM["co03_peak_k"] = round(max(p[1] for p in series) / 1e3, 1)


# ------------------------------------------------------------------------------------ 6 night
def fig_night(T, theme):
    rows = [r for r in fp["minute"] if "2026-11-03T12:00" <= r[0] <= "2026-11-04T13:12" and r[2]]
    t = [et(utc(r[0])) for r in rows]
    eq = np.array([r[2] for r in rows]) / 1e3
    cash = np.array([r[1] for r in rows]) / 1e3
    fig, (a, b) = plt.subplots(2, 1, figsize=(11, 5.8), sharex=True, gridspec_kw={"height_ratios": [3, 1], "hspace": 0.12})
    a.plot(t, eq, color=T["s"][0], lw=1.8)
    for hh, txt in ((18, "6 pm: first polls close"), (24, "midnight")):
        x = dt.datetime(2026, 11, 3) + dt.timedelta(hours=hh)
        a.axvline(x, color=T["axis"], lw=0.9, ls=(0, (3, 3)))
        a.text(x, 0.98, " " + txt, transform=a.get_xaxis_transform(), fontsize=9, color=T["muted"], va="top")
    for i, al in ((0, "left"), (len(eq) - 1, "right")):
        a.annotate(f"{eq[i]:.1f}k", (t[i], eq[i]), xytext=(0, 8), textcoords="offset points", ha=al, fontsize=9.5,
                   color=T["ink"])
    kfmt(a)
    hours = round((t[-1] - t[0]).total_seconds() / 3600)
    a.set_title(f"Election night: {eq[0]:.1f}k to {eq[-1]:.1f}k in {hours} hours")
    subtitle(a, "Account value at fair each minute, 7 am Nov 3 – 8:12 am Nov 4 ET", T)
    b.fill_between(t, 0, cash, color=T["s"][2], alpha=0.35, lw=0)
    b.plot(t, cash, color=T["s"][2], lw=1.1)
    b.set_ylabel("Cash")
    kfmt(b)
    b.xaxis.set_major_formatter(mdates.DateFormatter("%-I %p"))
    save(fig, "night", theme)
    NUM["night"] = {"start_k": round(float(eq[0]), 1), "end_k": round(float(eq[-1]), 1)}


# ------------------------------------------------------------------------------------ 7 leaderboard
def fig_leaderboard(T, theme):
    rows = [r for r in lb["rows"] if r.get("volume")]
    vol = np.array([r["volume"] for r in rows])
    pnl = np.array([r["pnl"] for r in rows]) / 1e3
    me = next(r for r in rows if r["username"] == "bright-dawn-8174")
    fig, ax = plt.subplots(figsize=(11, 5.6))
    ax.scatter(vol, pnl, s=10, color=T["gray"], alpha=0.6, lw=0, rasterized=True)
    top = sorted(rows, key=lambda r: r["rank"])[:5]
    ax.scatter([r["volume"] for r in top], [r["pnl"] / 1e3 for r in top], s=34, color=T["s"][0], edgecolor=T["bg"], lw=0.8)
    for r in top:
        ax.annotate(f"#{r['rank']} {r['username'].rsplit('-', 1)[0]}", (r["volume"], r["pnl"] / 1e3), xytext=(7, -3),
                    textcoords="offset points", fontsize=9, color=T["ink"])
    ax.scatter([me["volume"]], [me["pnl"] / 1e3], s=70, color=T["s"][1], edgecolor=T["bg"], lw=1.2, zorder=5)
    ax.annotate(f"us: #{me['rank']}, {me['pnl'] / 1e3:+.0f}k", (me["volume"], me["pnl"] / 1e3), xytext=(-10, 16),
                textcoords="offset points", ha="right", fontsize=10, color=T["ink"], fontweight="bold")
    ax.set_xscale("log")
    ax.set_xlim(1e3, 6e7)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1e6:g}M" if v >= 1e6 else f"{v / 1e3:g}k"))
    kfmt(ax)
    ax.axhline(0, color=T["axis"], lw=1)
    ax.set_xlabel("Volume traded (log scale)")
    ax.set_ylabel("P&L")
    ax.set_title(f"All {len(lb['rows']):,} ranked accounts: volume against P&L")
    subtitle(ax, f"SIG leaderboard on Nov 9, with {lb['meta']['settled']} of 237 markets settled", T)
    save(fig, "leaderboard", theme)
    NUM["board"] = {"rank": me["rank"], "pnl": round(me["pnl"]), "n": len(lb["rows"]), "settled": lb["meta"]["settled"],
                    "top": [(r["username"], round(r["pnl"]), round(r["volume"])) for r in top]}


# ------------------------------------------------------------------------------------ 8 markets
def fig_markets(T, theme):
    pm = sorted(((v[0], k) for k, v in fp["pnl_market"].items()), reverse=True)
    sel = pm[:14] + pm[-8:]
    fig, ax = plt.subplots(figsize=(10, 6.6))
    yy = np.arange(len(sel))[::-1]
    v = np.array([s[0] for s in sel]) / 1e3
    ax.barh(yy, v, 0.7, color=[T["s"][0] if x >= 0 else T["s"][1] for x in v], edgecolor=T["bg"], lw=1)
    ax.set_yticks(yy, [label(s[1]) for s in sel])
    for yi, vi in zip(yy, v):
        ax.text(vi + (0.6 if vi >= 0 else -0.6), yi, f"{vi:+.1f}k", va="center", ha="left" if vi >= 0 else "right",
                fontsize=8.8, color=T["ink"])
    ax.axvline(0, color=T["axis"], lw=1)
    ax.grid(axis="y", visible=False)
    kfmt(ax, "x")
    ax.set_xlim(min(v) - 6, max(v) + 6)
    ax.set_title("Best and worst markets, at the results")
    subtitle(ax, f"Top 14 and bottom 8 of the {len(pm)} markets we traded", T)
    save(fig, "markets", theme)
    NUM["markets_traded"] = len(pm)


# ------------------------------------------------------------------------------------ 9 who forecast best
def brier_by_day():
    days, out = [], defaultdict(list)
    for d in range(35):
        m0 = d * 1440 + 16 * 60                         # noon ET (16:00 UTC; 17:00 after Nov 1)
        if d >= 31:
            m0 += 60
        if d == 0:
            m0 += 60                                    # Oct 1: trading opened at noon, sample 1 pm
        sl = slice(m0 - 15, m0 + 15)
        vals = {k: np.nanmedian(a[:, sl], axis=1) for k, a in (("Kalshi", kal), ("Polymarket", pol),
                                                               ("Our fair", fair), ("SIG crowd", smid))}
        ok = np.isfinite(y) & np.all([np.isfinite(v) for v in vals.values()], axis=0)
        days.append(dt.datetime(2026, 10, 1) + dt.timedelta(days=d))
        for k, v in vals.items():
            out[k].append(float(np.mean((v[ok] - y[ok]) ** 2)))
        out["n"].append(int(ok.sum()))
    return days, out


def fig_accuracy(T, theme):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        days, b = brier_by_day()
    days, b = days[:34], {k: v[:34] for k, v in b.items()}     # stop at Nov 3: by noon Nov 4 most races were called
    fig, ax = plt.subplots(figsize=(11, 4.6))
    cols = {"Kalshi": T["s"][0], "Polymarket": T["s"][2], "Our fair": T["ink"], "SIG crowd": T["s"][1]}
    for k in ("SIG crowd", "Kalshi", "Polymarket", "Our fair"):
        ax.plot(days, b[k], color=cols[k], lw=2 if k != "Our fair" else 1.3, ls="-" if k != "Our fair" else (0, (3, 2)),
                marker="o", ms=3.5, label=k)
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.TH))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d"))
    ax.set_ylabel("Brier score (lower is better)")
    ax.legend(loc="lower left", ncol=4)
    ax.set_title("Who forecast the midterms best?")
    subtitle(ax, f"Each venue's noon price, Oct 1 – Nov 3, for the {b['n'][-1]} markets with a known result, "
                 "scored against that result", T)
    save(fig, "accuracy", theme)
    NUM["brier"] = {k: {"oct1": round(v[0], 4), "oct15": round(v[14], 4), "oct20": round(v[19], 4), "oct22": round(v[21], 4),
                        "nov3": round(v[33], 4), "mean": round(float(np.mean(v)), 4)} for k, v in b.items() if k != "n"}
    NUM["brier_n"] = b["n"][33]
    NUM["brier_sig_worst_days"] = int(sum(b["SIG crowd"][d] == max(b[k][d] for k in ("Kalshi", "Polymarket", "Our fair", "SIG crowd"))
                                          for d in range(34)))


# ------------------------------------------------------------------------------------ 10 longshot bias
def fig_longshot(T, theme):
    sl = slice(1440, 33 * 1440, 10)                    # Oct 2 - Nov 2, every 10 minutes
    f, s = fair[:, sl].ravel(), smid[:, sl].ravel()
    ok = np.isfinite(f) & np.isfinite(s)
    f, g = f[ok], (s[ok] - f[ok]) * 100
    edges = [0, .02, .05, .1, .2, .35, .5, .65, .8, .9, .95, .98, 1.0001]
    xs, med, lo, hi, n = [], [], [], [], []
    for a_, b_ in zip(edges[:-1], edges[1:]):
        m = (f >= a_) & (f < b_)
        xs.append(f[m].mean() * 100)
        q = np.percentile(g[m], [25, 50, 75])
        lo.append(q[0]); med.append(q[1]); hi.append(q[2]); n.append(int(m.sum()))
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.axhline(0, color=T["axis"], lw=1)
    ax.vlines(xs, lo, hi, color=T["s"][0], lw=6, alpha=0.3)
    ax.plot(xs, med, color=T["s"][0], lw=2, marker="o", ms=6, mec=T["bg"], mew=1.5)
    ax.set_xlabel("Fair probability (Kalshi + Polymarket), %")
    ax.set_ylabel("SIG price minus fair (points)")
    ax.set_xlim(0, 100)
    ax.text(3, max(hi) * 0.92, "Longshots cost too much on SIG", fontsize=9.5, color=T["muted"])
    ax.text(97, min(lo) * 0.92, "Favorites were too cheap", fontsize=9.5, color=T["muted"], ha="right")
    ax.set_title("SIG's longshot bias, all month")
    subtitle(ax, "Median gap (line) and middle half (band) across all markets, sampled every 10 minutes, Oct 2 – Nov 2", T)
    save(fig, "longshot", theme)
    NUM["longshot"] = {f"{e0:.2f}-{e1:.2f}": round(m, 2) for e0, e1, m in zip(edges[:-1], edges[1:], med)}
    # what buying every SIG longshot would have done: SIG price vs fair vs result, Nov 1 noon
    m0 = 31 * 1440 + 17 * 60
    sp, fp_ = np.nanmedian(smid[:, m0 - 15:m0 + 15], axis=1), np.nanmedian(fair[:, m0 - 15:m0 + 15], axis=1)
    ok = np.isfinite(sp) & np.isfinite(fp_) & np.isfinite(y) & (sp < 0.10)
    NUM["longshots_nov1"] = {"n": int(ok.sum()), "sig_avg": round(float(sp[ok].mean()), 3),
                             "fair_avg": round(float(fp_[ok].mean()), 3), "won": round(float(y[ok].mean()), 3)}


# ------------------------------------------------------------------------------------ 11 efficiency
def fig_efficiency(T, theme):
    import warnings
    days, med, p90, share = [], [], [], []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for d in range(35):
            sl = slice(d * 1440 + (960 if d == 0 else 0), (d + 1) * 1440, 5)   # Oct 1 from the noon open
            g = np.abs(smid[:, sl] - fair[:, sl]).ravel() * 100
            g = g[np.isfinite(g)]
            days.append(dt.datetime(2026, 10, 1) + dt.timedelta(days=d))
            med.append(float(np.median(g))); p90.append(float(np.percentile(g, 90))); share.append(float((g >= 2).mean() * 100))
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"wspace": 0.25})
    a.plot(days, p90, color=T["s"][1], lw=2, marker="o", ms=3, label="90th percentile")
    a.plot(days, med, color=T["s"][0], lw=2, marker="o", ms=3, label="Median")
    a.set_ylim(bottom=0)
    a.set_ylabel("|SIG mid − fair|, points")
    a.legend(loc="upper right")
    a.set_title("SIG's distance from fair, by day")
    b.plot(days, share, color=T["s"][0], lw=2, marker="o", ms=3)
    b.set_ylim(0, 100)
    b.set_ylabel("% of market-minutes")
    b.set_title("Time spent 2+ points off fair")
    for ax in (a, b):
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.TH))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d"))
    save(fig, "efficiency", theme)
    NUM["efficiency"] = {"median_oct1": round(med[0], 2), "median_oct8": round(med[7], 2), "median_oct31": round(med[30], 2),
                         "p90_oct1": round(p90[0], 1), "p90_oct31": round(p90[30], 1),
                         "share2_oct1": round(share[0]), "share2_oct8": round(share[7]), "share2_oct31": round(share[30])}


# ------------------------------------------------------------------------------------ 12 election night lag
def ffill(a):
    a = a.copy()
    for i in range(1, len(a)):
        if not np.isfinite(a[i]):
            a[i] = a[i - 1]
    return a


def fig_lag(T, theme):
    step = int(NI["step"])
    k_all, p_all = NI["kalshi"], NI["poly"]
    s_all = sig_mid(NI["sig_bid"], NI["sig_ask"], 0.3)
    W0, W1 = -30 * 60 // step, 180 * 60 // step
    paths, lags_p, lags_s, used = defaultdict(list), [], [], []
    for i, name in enumerate(names):
        k, p, s = ffill(k_all[i]), ffill(p_all[i]), ffill(s_all[i])
        if not np.isfinite(k[:180]).any() or not np.isfinite(y[i]):
            continue
        start = np.nanmedian(k[:180])                    # 6:00-6:30 pm ET
        move = y[i] - start
        if abs(move) < 0.3:
            continue
        prog = {n: (v - start) / move for n, v in (("Kalshi", k), ("Polymarket", p), ("SIG", s))}
        cross = {n: np.argmax(np.nan_to_num(v, nan=-9) >= 0.5) if (np.nan_to_num(v, nan=-9) >= 0.5).any() else None
                 for n, v in prog.items()}
        if cross["Kalshi"] is None or cross["Kalshi"] < 180:
            continue
        c0 = cross["Kalshi"]
        used.append(name)
        if cross["Polymarket"] is not None:
            lags_p.append((cross["Polymarket"] - c0) * step / 60)
        if cross["SIG"] is not None:
            lags_s.append((cross["SIG"] - c0) * step / 60)
        for n, v in prog.items():
            seg = np.full(W1 - W0, np.nan)
            lo, hi = c0 + W0, c0 + W1
            src = v[max(lo, 0):min(hi, len(v))]
            seg[max(lo, 0) - lo:max(lo, 0) - lo + len(src)] = src
            paths[n].append(np.clip(seg, -0.25, 1.25))
    x = np.arange(W0, W1) * step / 60
    fig, ax = plt.subplots(figsize=(11, 4.8))
    cols = {"Kalshi": T["s"][0], "Polymarket": T["s"][2], "SIG": T["s"][1]}
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for n in ("Kalshi", "Polymarket", "SIG"):
            arr = np.array(paths[n])
            q1, q2, q3 = np.nanpercentile(arr, [25, 50, 75], axis=0)
            if n == "SIG":
                ax.fill_between(x, q1, q3, color=cols[n], alpha=0.15, lw=0, label="SIG, middle half of races")
            ax.plot(x, q2, color=cols[n], lw=2.2, label=n)
    ax.axvline(0, color=T["axis"], lw=1, ls=(0, (3, 3)))
    ax.axhline(0.5, color=T["axis"], lw=0.8)
    ax.set_ylim(-0.1, 1.1)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlabel("Minutes from the moment Kalshi had priced half of the race's final move")
    ax.set_ylabel("Share of the move priced in")
    ax.legend(loc="lower right")
    ax.set_title("Election night: Kalshi moved first, SIG last")
    subtitle(ax, f"{len(used)} markets that moved 30+ points after 5:30 pm ET. Median across races.", T)
    save(fig, "night_lag", theme)
    NUM["lag"] = {"n": len(used), "poly_median_min": round(float(np.median(lags_p)), 1),
                  "sig_median_min": round(float(np.median(lags_s)), 1),
                  "sig_p75_min": round(float(np.percentile(lags_s, 75)), 1), "n_sig": len(lags_s)}


# ------------------------------------------------------------------------------------ 13 markouts
def fig_markouts(T, theme):
    H = [("At fill", 0), ("1 min", 1), ("10 min", 10), ("1 h", 60), ("6 h", 360), ("1 day", 1440)]
    acc = defaultdict(lambda: np.zeros(len(H) + 1))
    wts = defaultdict(lambda: np.zeros(len(H) + 1))
    for ts, m, side, px, q, f0, why in fp["fills"]:
        i = idx.get(m)
        if i is None or f0 is None:
            continue
        g = GROUP.get(why, "Quotes")
        sgn = 1 if side == "bid" else -1
        m0 = int((utc(ts) - T0).total_seconds() // 60)
        for j, (_, h) in enumerate(H):
            fv = f0 if h == 0 else (fair[i, m0 + h] if m0 + h < fair.shape[1] else np.nan)
            if np.isfinite(fv):
                acc[g][j] += sgn * (fv - px) * q
                wts[g][j] += q
        if np.isfinite(y[i]):
            acc[g][-1] += sgn * (y[i] - px) * q
            wts[g][-1] += q
    labels = [h[0] for h in H] + ["Result"]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    cols = {"Takes": T["s"][0], "Event sweeps": T["s"][1], "Quotes": T["s"][2], "Exits at fair": T["s"][3],
            "Paid exits": T["s"][4]}
    out = {}
    for g in ("Takes", "Event sweeps", "Quotes", "Exits at fair", "Paid exits"):
        v = acc[g] / np.maximum(wts[g], 1) * 100
        ax.plot(range(len(labels)), v, color=cols[g], lw=2, marker="o", ms=5, mec=T["bg"], mew=1.2, label=g)
        out[g] = [round(float(a), 2) for a in v]
    ax.axhline(0, color=T["axis"], lw=1)
    ax.set_xticks(range(len(labels)), labels)
    ax.set_ylabel("Edge per share in our favour (points)")
    ax.legend(loc="upper left", ncol=3)
    ax.set_title("Did the edge hold after the fill?")
    subtitle(ax, "Fair value at each horizon after every fill, minus the fill price, weighted by shares", T)
    save(fig, "markouts", theme)
    NUM["markouts"] = out


FIGS = [fig_equity, fig_daily, fig_purpose, fig_day1, fig_co03, fig_night, fig_leaderboard, fig_markets,
        fig_accuracy, fig_longshot, fig_efficiency, fig_lag, fig_markouts]

if __name__ == "__main__":
    import sys
    only = set(sys.argv[1:])
    for fn in FIGS:
        if only and fn.__name__[4:] not in only:
            continue
        for theme, T in THEMES.items():
            style(T)
            fn(T, theme)
        print("drew", fn.__name__[4:], flush=True)
    json.dump(NUM, open(DATA / "numbers.json", "w"), indent=1, default=str)
    print(json.dumps(NUM, indent=1, default=str))
