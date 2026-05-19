"""
v77_smile_hybrid — v77_r4 base + per-tick parabolic vol smile + smile-relative MR.

Key insight from a top R3 team's writeup (githubreadme intel):
  1. Fit a parabola IV(m_t) across strikes per tick where m_t = log(K/S)/sqrt(T)
  2. The smile parabola is stable; deviations IV_observed - IV_smile show 1-lag
     negative autocorrelation → mean-reversion alpha
  3. Convert smile-IV back to a theoretical fair price BS(S, K, T, σ_smile)
  4. Trade MR around this dynamic theoretical fair (NOT a static rolling mean)
  5. Smile-fair MOVES with VF and accommodates strike structure → tighter, more
     profitable fair than v77_r4's rolling mean.

Design:
  - Keep v77_r4's HG/VF MR exactly (proven $160k base alpha).
  - Replace _atm_mr's rolling-mean fair with blended smile + rolling.
  - Per-tick: bisect IV per strike → fit quadratic across ATM strikes →
    smile-fair-price = BS(σ_smile) → blend with rolling for stability.
"""
from math import floor, ceil, log, sqrt, exp, erf
import json
import math
from typing import Any, Dict, List, Optional, Tuple

try:
    from prosperity3bt.datamodel import (
        Listing, Observation, Order, OrderDepth, ProsperityEncoder,
        Symbol, Trade, TradingState,
    )
except ModuleNotFoundError:
    from datamodel import (
        Listing, Observation, Order, OrderDepth, ProsperityEncoder,
        Symbol, Trade, TradingState,
    )


# ─── Black-Scholes helpers ──────────────────────────────────────────────────

def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def bs_call(S: float, K: float, T: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0 or S <= 0:
        return max(S - K, 0.0)
    sq = sigma * sqrt(T)
    d1 = (log(S / K) + 0.5 * sigma * sigma * T) / sq
    d2 = d1 - sq
    return S * norm_cdf(d1) - K * norm_cdf(d2)


def bs_call_delta(S: float, K: float, T: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0 or S <= 0:
        return 1.0 if S > K else 0.0
    sq = sigma * sqrt(T)
    d1 = (log(S / K) + 0.5 * sigma * sigma * T) / sq
    return norm_cdf(d1)


def implied_vol(market_price: float, S: float, K: float, T: float,
                lo: float = 0.001, hi: float = 4.0, max_iter: int = 30,
                tol: float = 0.01) -> Optional[float]:
    """Bisection to find sigma so bs_call(S,K,T,σ) ≈ market_price."""
    intrinsic = max(S - K, 0.0)
    if market_price < intrinsic - 0.5:
        return None
    if market_price < intrinsic + 0.05:
        return 0.001
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        p = bs_call(S, K, T, mid)
        if abs(p - market_price) < tol:
            return mid
        if p < market_price:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def fit_quadratic(xs: List[float], ys: List[float]) -> Optional[Tuple[float, float, float]]:
    """Least-squares fit y = a*x^2 + b*x + c. Returns (a,b,c) or None."""
    n = len(xs)
    if n < 3:
        return None
    S0 = float(n); S1 = sum(xs); S2 = sum(x*x for x in xs)
    S3 = sum(x*x*x for x in xs); S4 = sum(x*x*x*x for x in xs)
    T0 = sum(ys); T1 = sum(x*y for x, y in zip(xs, ys))
    T2 = sum(x*x*y for x, y in zip(xs, ys))
    # 3x3 system: [[S4,S3,S2],[S3,S2,S1],[S2,S1,S0]] @ [a,b,c] = [T2,T1,T0]
    def det3(m):
        return (m[0][0]*(m[1][1]*m[2][2] - m[1][2]*m[2][1])
              - m[0][1]*(m[1][0]*m[2][2] - m[1][2]*m[2][0])
              + m[0][2]*(m[1][0]*m[2][1] - m[1][1]*m[2][0]))
    M = [[S4, S3, S2], [S3, S2, S1], [S2, S1, S0]]
    Y = [T2, T1, T0]
    D = det3(M)
    if abs(D) < 1e-12:
        return None
    Ma = [[Y[0], S3, S2], [Y[1], S2, S1], [Y[2], S1, S0]]
    Mb = [[S4, Y[0], S2], [S3, Y[1], S1], [S2, Y[2], S0]]
    Mc = [[S4, S3, Y[0]], [S3, S2, Y[1]], [S2, S1, Y[2]]]
    return (det3(Ma) / D, det3(Mb) / D, det3(Mc) / D)


# ─── Logger (identical to v77_r4) ───────────────────────────────────────────

class Logger:
    def __init__(self):
        self.logs = ""
        self.max_log_length = 3750
    def print(self, *objects, sep=" ", end="\n"):
        self.logs += sep.join(map(str, objects)) + end
    def flush(self, state, orders, conversions, trader_data):
        base_length = len(self.to_json([self.compress_state(state, ""), self.compress_orders(orders), conversions, "", ""]))
        max_item_length = (self.max_log_length - base_length) // 3
        print(self.to_json([self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                            self.compress_orders(orders), conversions,
                            self.truncate(trader_data, max_item_length),
                            self.truncate(self.logs, max_item_length)]))
        self.logs = ""
    def compress_state(self, state, trader_data):
        return [state.timestamp, trader_data, self.compress_listings(state.listings),
                self.compress_order_depths(state.order_depths), self.compress_trades(state.own_trades),
                self.compress_trades(state.market_trades), state.position, self.compress_observations(state.observations)]
    def compress_listings(self, ls): return [[l.symbol, l.product, l.denomination] for l in ls.values()]
    def compress_order_depths(self, ods): return {s: [od.buy_orders, od.sell_orders] for s, od in ods.items()}
    def compress_trades(self, trades):
        out = []
        for tl in trades.values():
            for t in tl: out.append([t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp])
        return out
    def compress_observations(self, obs):
        co = {}
        for p, o in obs.conversionObservations.items():
            co[p] = [o.bidPrice, o.askPrice, o.transportFees, o.exportTariff, o.importTariff]
        return [obs.plainValueObservations, co]
    def compress_orders(self, orders):
        out = []
        for ol in orders.values():
            for o in ol: out.append([o.symbol, o.price, o.quantity])
        return out
    def to_json(self, value): return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))
    def truncate(self, value, max_length):
        v = value or ""; lo, hi = 0, min(len(v), max_length); out = ""
        while lo <= hi:
            mid = (lo + hi) // 2; cand = v[:mid] + ("..." if mid < len(v) else "")
            if len(json.dumps(cand)) <= max_length: out = cand; lo = mid + 1
            else: hi = mid - 1
        return out

logger = Logger()


# ─── Trader ─────────────────────────────────────────────────────────────────

class Trader:
    POS_LIMIT = {'HYDROGEL_PACK': 200, 'VELVETFRUIT_EXTRACT': 200}
    OPT_LIMIT = 300
    WARMUP_TICKS = 50
    WARMUP_EDGE_MULT = 5.0

    HG_TRAINING_MEAN = 9994
    VF_TRAINING_MEAN = 5247
    HG_OFFSET = 26
    VF_OFFSET = 7
    DETECT_WINDOW = 2000
    HG_DRIFT_TOL = 8
    VF_DRIFT_TOL = 5

    HG_OU_MU = 9988
    VF_OU_MU = 5240
    HG_IMBAL_SHIFT = -3  # tuned on 6-day MIN (was -5 from iter cycle 9)
    VF_IMBAL_SHIFT = 0

    # Dynamic anchor: blend static HG_OU_MU with rolling-mean of HG mids.
    # Helps when production day's HG mean drifts ±5 from training (MC test
    # showed ~$10k MIN loss per ±3 shift). 0.0 = pure static, 1.0 = pure rolling.
    HG_DYNAMIC_BLEND = 0.0  # off by default; enable when MC says it helps
    VF_DYNAMIC_BLEND = 0.0
    DYN_ANCHOR_WINDOW = 2000  # rolling window for dynamic anchor

    # === Voucher / smile config ===
    # All voucher strikes traded by v77_r4
    TRADE_STRIKES = {'VEV_4000': 4000, 'VEV_4500': 4500, 'VEV_5000': 5000,
                     'VEV_5100': 5100, 'VEV_5200': 5200, 'VEV_5300': 5300,
                     'VEV_5400': 5400, 'VEV_5500': 5500}
    # Strikes used to FIT the smile parabola (need well-defined IV)
    SMILE_FIT_STRIKES = {'VEV_4500': 4500, 'VEV_5000': 5000, 'VEV_5100': 5100,
                         'VEV_5200': 5200, 'VEV_5300': 5300, 'VEV_5400': 5400,
                         'VEV_5500': 5500, 'VEV_6000': 6000}
    # Smile bias only applied to strikes whose moneyness is within this range
    SMILE_BIAS_M_RANGE = 0.7   # |log(K/S)/sqrt(T)| <= this → apply smile
    HEDGE_STRIKES = {'VEV_5000': 5000, 'VEV_5100': 5100, 'VEV_5200': 5200,
                     'VEV_5300': 5300, 'VEV_5400': 5400, 'VEV_5500': 5500}

    # Per-strike clip map for normal days. Tightening only VEV_5300
    # (closest-to-ATM at S=5247, highest gamma) to clip=2 boosts MIN.
    # Other strikes at uniform clip=10.
    OPT_CLIP_MAP = {'VEV_4000': 10, 'VEV_4500': 10, 'VEV_5000': 10,
                    'VEV_5100': 10, 'VEV_5200': 10, 'VEV_5300': 2,
                    'VEV_5400': 10, 'VEV_5500': 10}
    # On hard days (R4_d3-like regime) override these strikes' clips.
    # Bigger clips on 5200/5300 capture more on the directional drift
    # without paying the noise cost we'd see on calm days.
    HARD_DAY_CLIP_OVERRIDES = {'VEV_4000': 15, 'VEV_5200': 40, 'VEV_5300': 30}
    USE_OPT_CLIP_MAP = True

    # Day-type detection: R4_d3 had first-1000-tick HG mean ≈ 10033 vs
    # 9958-9982 for the other 3 known days — wide separation. When the early
    # HG average exceeds HARD_DAY_HG_THRESHOLD, classify as "hard day" and
    # apply HARD_DAY_OPT_INV_SKEW (tighter inventory skew on vouchers,
    # earlier exit on long inventory). Threshold=10000 is conservative —
    # only fires on R4_d3-like regimes.
    DETECT_TICK = 1000
    HARD_DAY_HG_THRESHOLD = 10000.0
    HARD_DAY_OPT_INV_SKEW = 0.012  # max-EV tuned (was 0.025)
    HARD_DAY_SMILE_BIAS_W = 12.0  # vs default 1.0
    HARD_DAY_SMILE_IV_EMA = 1.0   # no smoothing on hard day (raw signal best)
    HARD_DAY_SMILE_M_RANGE = 3.0  # include all strikes in smile bias on hard day
    HARD_DAY_SMILE_BIAS_CAP = 4.0 # vs default 3.0
    ENABLE_DAY_DETECT = True

    # "Soft-high-VF" day detection: R4_d2 had VF first-1000-tick ≈ 5262 with
    # HG ≈ 9979 (normal). R3_d0/R4_d1 had VF ~5238-5240. Threshold ~5250
    # catches R4_d2-like regimes (and also R4_d3, but hard-day check fires
    # first and takes precedence).
    SOFT_HIGH_VF_THRESHOLD = 5250.0
    ENABLE_SOFT_HIGH_VF_DETECT = True
    SOFT_HIGH_VF_CLIP_OVERRIDES = {'VEV_5200': 8, 'VEV_5300': 30}
    # On soft-high-VF days, run a NEGATIVE inv_skew (slight long bias on
    # voucher inventory). VF tends to drift further up on these days, so
    # holding/extending long voucher positions captures the move.
    SOFT_HIGH_VF_OPT_INV_SKEW = -0.010

    # TTE in years; R4 starts at 4 days. Decay linearly each tick.
    TTE_DAYS_AT_START = 4.0
    YEAR = 252.0

    # Smile-bias as ADDITIVE to v77_r4 rolling-mean fair:
    #   fair = rolling_mean + clamp(SMILE_BIAS_W * (smile_fair - mid), ±cap)
    # 0.0 reproduces v77_r4 exactly. With the day-detect clip overrides
    # active, the optimal sign flipped to POSITIVE (cross-strike residual
    # behaves like fundamental mispricing — fade toward smile).
    SMILE_BIAS_W = 5.0
    SMILE_MIN_POINTS = 4
    SMILE_MIN_IV = 0.05
    SMILE_MAX_IV = 1.5
    SMILE_BIAS_CAP = 1.5
    SMILE_BIAS_M_RANGE = 1.5  # avoids overfit; only ATM-ish strikes

    # Per-strike EMA smoothing of smile-IV. α=0.55 tuned (+$484 vs raw).
    SMILE_IV_EMA_ALPHA = 0.40

    # Smile mode: 'parabola' (per-tick fit) or 'static' (use calibrated σ table)
    SMILE_MODE = 'parabola'

    # Whale signal (Mark 49 sell / Mark 67 buy / Mark 22 sell VF → +$2-3 in 50 ticks).
    # Empirically validated bullish bias on VF after these named-trader prints.
    # Disabled on hard days where the post-shock revert weakens.
    WHALE_BIAS = 3.0
    WHALE_TICKS = 50
    WHALE_INCLUDE_MARK_22 = True

    # AGGRESSIVE Mark 67 BUY-follow: continuous lift across the signal window
    # paid spread every tick and destroyed PnL. Fire ONLY on the event tick
    # (whale_just_fired) per v78 — way less spread cost.
    WHALE_FORCE_TAKE = True
    WHALE_FORCE_QTY = 35
    AGGRO_FOLLOW_M67 = False  # legacy continuous-lift; left disabled
    AGGRO_M67_LIFT_CLIP = 25
    AGGRO_M67_TICKS = 30
    AGGRO_M67_DISABLED_HARD = True

    # HG whale: Mark 38 BUY HG or Mark 14 SELL HG → HG mean -$1.1 in 50 ticks
    # (t≈-1.95). Apply BEARISH bias to HG fair → makes us sell more aggressively.
    HG_WHALE_BIAS = 0.0  # disabled: hurts AVG by $1k+ in max-EV regime
    HG_WHALE_TICKS = 50
    # Per-strike σ calibrated from /tmp/calibrate_iv.py (median across 4 days).
    # These are stable: ATM ≈ 0.19, ITM 4500 ≈ 0.38, wings 0.30+
    STATIC_IV = {
        'VEV_4000': 0.66, 'VEV_4500': 0.38, 'VEV_5000': 0.193,
        'VEV_5100': 0.190, 'VEV_5200': 0.193, 'VEV_5300': 0.196,
        'VEV_5400': 0.184, 'VEV_5500': 0.199, 'VEV_6000': 0.331,
        'VEV_6500': 0.500,
    }

    # Delta-hedge layer (off by default in v1; toggled by ENABLE_DELTA_HEDGE)
    ENABLE_DELTA_HEDGE = False
    HEDGE_THRESHOLD = 15
    HEDGE_VF_RESERVE = 80   # max VF position consumed by hedge (rest reserved for MR)

    MAKE_LADDER_OFFSETS = [1, 2, 3]
    MAKE_LADDER_CLIPS = {'HYDROGEL_PACK': [50, 40, 30], 'VELVETFRUIT_EXTRACT': [40, 35, 25]}
    SHOCK_THRESHOLD = 3.0
    SHOCK_FADE_COEF = 0.30

    LOCK_MODE: str = 'D'
    LOCK_PCT: float = 0.25
    LOCK_ABS: float = 20000.0
    LOCK_TICK: int = 9999
    LOCK_REDUCE: float = 0.5
    LOCK_MIN_PEAK: float = 50000.0

    def __init__(self):
        self.hg_edge = 20
        self.hg_inv_skew = -0.06  # tightened for max-EV
        self.hg_soft_cap = 200
        self.hg_take_clip = 50
        self.hg_make_clip = 70
        self.hg_prev_mid: Optional[float] = None

        self.vf_mids: List[float] = []
        self.vf_window = 1500
        self.vf_edge = 9  # tightened edge for higher EV
        self.vf_inv_skew = 0.0
        self.vf_soft_cap = 200
        self.vf_take_clip = 25  # tuned for max-EV
        self.vf_make_clip = 60
        self.vf_prev_mid: Optional[float] = None

        # Voucher rolling-mean MR state.
        # opt_inv_skew tuned up to 0.055 (a heavier inventory penalty) — works
        # in concert with the smile bias / clip-map / day-detect layers.
        self.opt_mids: dict = {}
        self.opt_window = 9000
        self.opt_inv_skew = 0.005
        self.opt_soft_cap = 300
        self.opt_edge_v77 = 8  # tighter voucher edge for max-EV
        self.opt_take_clip_v77 = 10
        # Per-strike EMA-smoothed smile σ (filled lazily)
        self._smile_iv_ema: Dict[str, float] = {}
        # Day-type detection state
        self._hg_mids: List[float] = []
        self._vf_early_mids: List[float] = []
        self._day_classified: bool = False
        self._is_hard_day: bool = False
        self._is_soft_high_vf: bool = False

        self._cash: Dict[str, float] = {}
        self._max_pnl: float = 0.0
        self._lock_active: bool = False

        self._hg_active_anchor: float = self.HG_OU_MU
        self._vf_active_anchor: float = self.VF_OU_MU

    def encode_trader_data(self, state):
        return json.dumps({'vf': self.vf_mids, 'hpm': self.hg_prev_mid, 'vpm': self.vf_prev_mid})
    def decode_trader_data(self, s):
        if not s: return
        try:
            d = json.loads(s)
            if isinstance(d.get('vf'), list): self.vf_mids = [float(x) for x in d['vf']]
            v = d.get('hpm')
            if v is not None: self.hg_prev_mid = float(v)
            v = d.get('vpm')
            if v is not None: self.vf_prev_mid = float(v)
        except: pass

    def _time_to_expiry(self, ts: int) -> float:
        # 1M timestamps per day, but iteration runs 10k ticks (each tick = 100 ts).
        # ts goes 0..999900 in steps of 100. So one full backtest day = 1 trading day.
        elapsed_days = ts / 1000000.0
        return max(0.001, (self.TTE_DAYS_AT_START - elapsed_days) / self.YEAR)

    def run(self, state):
        self.decode_trader_data(state.traderData)
        self._tick_count = getattr(self, "_tick_count", 0) + 1
        self._update_cash_from_trades(state)
        cur_pnl = self._compute_total_pnl(state)
        if cur_pnl > self._max_pnl: self._max_pnl = cur_pnl
        self._evaluate_lock(cur_pnl)
        orders: Dict[str, List[Order]] = {}
        self._hg(state, orders)
        self._vf(state, orders)
        self._smile_voucher_mr(state, orders)
        if self.ENABLE_DELTA_HEDGE:
            self._delta_hedge(state, orders)
        orders = self._apply_lock_filter(state, orders)
        trader_data = self.encode_trader_data(state)
        logger.flush(state, orders, 0, trader_data)
        return orders, 0, trader_data

    def _update_cash_from_trades(self, state):
        for sym, tlist in state.own_trades.items():
            for t in tlist:
                if t.buyer == 'SUBMISSION': self._cash[sym] = self._cash.get(sym, 0.0) - t.price * t.quantity
                else: self._cash[sym] = self._cash.get(sym, 0.0) + t.price * t.quantity
    def _compute_total_pnl(self, state):
        total = 0.0
        for prod, od in state.order_depths.items():
            if not od.buy_orders or not od.sell_orders: continue
            mid = (max(od.buy_orders.keys()) + min(od.sell_orders.keys())) / 2.0
            total += self._cash.get(prod, 0.0) + state.position.get(prod, 0) * mid
        return total
    def _evaluate_lock(self, cur_pnl):
        if self.LOCK_MODE == 'D': self._lock_active = (self._tick_count >= self.LOCK_TICK)
    def _apply_lock_filter(self, state, orders):
        if self.LOCK_MODE == 'none' or not self._lock_active: return orders
        new_orders = {}
        for sym, ol in orders.items():
            pos = state.position.get(sym, 0)
            kept = []
            for o in ol:
                if pos == 0: continue
                if pos > 0 and o.quantity < 0:
                    q = max(o.quantity, -pos)
                    if q != 0: kept.append(Order(o.symbol, o.price, q))
                elif pos < 0 and o.quantity > 0:
                    q = min(o.quantity, -pos)
                    if q != 0: kept.append(Order(o.symbol, o.price, q))
            if kept: new_orders[sym] = kept
        for sym, pos in state.position.items():
            if pos == 0 or sym in new_orders: continue
            if sym not in state.order_depths: continue
            od = state.order_depths[sym]
            if pos > 0:
                if od.buy_orders: new_orders[sym] = [Order(sym, max(od.buy_orders.keys()), -pos)]
            else:
                if od.sell_orders: new_orders[sym] = [Order(sym, min(od.sell_orders.keys()), -pos)]
        return new_orders

    def _ladder_makes(self, prod, best_bid, best_ask, fair_skewed, buy_room, sell_room):
        out = []
        clips = self.MAKE_LADDER_CLIPS.get(prod, [30, 20, 10])
        for off, clip in zip(self.MAKE_LADDER_OFFSETS, clips):
            if buy_room <= 0: break
            mb = best_bid + off
            if mb >= fair_skewed: break
            if mb >= best_ask: break
            qty = min(buy_room, clip)
            if qty > 0: out.append(Order(prod, mb, qty)); buy_room -= qty
        for off, clip in zip(self.MAKE_LADDER_OFFSETS, clips):
            if sell_room <= 0: break
            ma = best_ask - off
            if ma <= fair_skewed: break
            if ma <= best_bid: break
            qty = min(sell_room, clip)
            if qty > 0: out.append(Order(prod, ma, -qty)); sell_room -= qty
        return out

    def _l1_imbalance(self, od):
        bb = max(od.buy_orders.keys()); ba = min(od.sell_orders.keys())
        bv = od.buy_orders[bb]; av = abs(od.sell_orders[ba])
        tot = bv + av
        return (bv - av) / tot if tot > 0 else 0.0

    def _shock_shift(self, cur_mid, prev_mid):
        if prev_mid is None: return 0.0
        r = cur_mid - prev_mid
        if abs(r) < self.SHOCK_THRESHOLD: return 0.0
        return -self.SHOCK_FADE_COEF * r

    def _hg(self, state, orders):
        prod = 'HYDROGEL_PACK'
        if prod not in state.order_depths: return
        od = state.order_depths[prod]
        if not od.buy_orders or not od.sell_orders: return
        best_bid = max(od.buy_orders.keys()); best_ask = min(od.sell_orders.keys())
        best_bid_vol = od.buy_orders[best_bid]; best_ask_vol = abs(od.sell_orders[best_ask])
        mid = (best_bid + best_ask) / 2.0
        # HG whale signal: Mark 38 BUY or Mark 14 SELL → HG drops -$1.1 in 50 ticks
        if not hasattr(self, '_hg_whale_signal'): self._hg_whale_signal = 0
        if self._hg_whale_signal > 0: self._hg_whale_signal -= 1
        for tr in state.market_trades.get(prod, []):
            if tr.buyer == 'Mark 38' or tr.seller == 'Mark 14':
                self._hg_whale_signal = self.HG_WHALE_TICKS
        hg_whale_bias = -self.HG_WHALE_BIAS if self._hg_whale_signal > 0 else 0.0
        # Day-type detection: collect early HG (and VF) mids, classify after DETECT_TICK
        if (self.ENABLE_DAY_DETECT or self.ENABLE_SOFT_HIGH_VF_DETECT) and not self._day_classified:
            self._hg_mids.append(mid)
            # Also collect VF mid for soft-high-VF detection
            vfod = state.order_depths.get('VELVETFRUIT_EXTRACT')
            if vfod is not None and vfod.buy_orders and vfod.sell_orders:
                self._vf_early_mids.append(
                    (max(vfod.buy_orders.keys()) + min(vfod.sell_orders.keys())) / 2.0)
            if self._tick_count >= self.DETECT_TICK:
                hg_avg = sum(self._hg_mids) / len(self._hg_mids)
                self._is_hard_day = (self.ENABLE_DAY_DETECT
                                     and hg_avg > self.HARD_DAY_HG_THRESHOLD)
                if self.ENABLE_SOFT_HIGH_VF_DETECT and not self._is_hard_day and self._vf_early_mids:
                    vf_avg = sum(self._vf_early_mids) / len(self._vf_early_mids)
                    self._is_soft_high_vf = (vf_avg > self.SOFT_HIGH_VF_THRESHOLD)
                self._day_classified = True
        imbal = self._l1_imbalance(od)
        shock = self._shock_shift(mid, self.hg_prev_mid)
        self.hg_prev_mid = mid
        # Dynamic anchor: blend static HG_OU_MU with rolling-mean of HG mids
        if not hasattr(self, '_hg_anchor_buf'): self._hg_anchor_buf = []
        if self.HG_DYNAMIC_BLEND > 0:
            self._hg_anchor_buf.append(mid)
            if len(self._hg_anchor_buf) > self.DYN_ANCHOR_WINDOW:
                del self._hg_anchor_buf[:len(self._hg_anchor_buf) - self.DYN_ANCHOR_WINDOW]
            roll = sum(self._hg_anchor_buf) / len(self._hg_anchor_buf)
            anchor = (1.0 - self.HG_DYNAMIC_BLEND) * self._hg_active_anchor + self.HG_DYNAMIC_BLEND * roll
        else:
            anchor = self._hg_active_anchor
        fair = anchor + self.HG_IMBAL_SHIFT * imbal + shock + hg_whale_bias
        pos = state.position.get(prod, 0)
        fair_skewed = fair - self.hg_inv_skew * pos
        edge = self.hg_edge
        hard = self.POS_LIMIT[prod]
        order_list = []
        buy_room = hard - pos; sell_room = hard + pos
        if best_ask < fair_skewed - edge and pos < self.hg_soft_cap:
            cap_room = min(buy_room, self.hg_soft_cap - pos + 30)
            qty = min(best_ask_vol, cap_room, self.hg_take_clip)
            if qty > 0: order_list.append(Order(prod, best_ask, qty)); buy_room -= qty
        if best_bid > fair_skewed + edge and pos > -self.hg_soft_cap:
            cap_room = min(sell_room, self.hg_soft_cap + pos + 30)
            qty = min(best_bid_vol, cap_room, self.hg_take_clip)
            if qty > 0: order_list.append(Order(prod, best_bid, -qty)); sell_room -= qty
        order_list.extend(self._ladder_makes(prod, best_bid, best_ask, fair_skewed, buy_room, sell_room))
        if order_list: orders[prod] = order_list

    def _vf(self, state, orders):
        prod = 'VELVETFRUIT_EXTRACT'
        if prod not in state.order_depths: return
        od = state.order_depths[prod]
        if not od.buy_orders or not od.sell_orders: return
        best_bid = max(od.buy_orders.keys()); best_ask = min(od.sell_orders.keys())
        best_bid_vol = od.buy_orders[best_bid]; best_ask_vol = abs(od.sell_orders[best_ask])
        mid = (best_bid + best_ask) / 2.0
        self.vf_mids.append(mid)
        if len(self.vf_mids) > self.vf_window:
            del self.vf_mids[:len(self.vf_mids) - self.vf_window]
        imbal = self._l1_imbalance(od)
        shock = self._shock_shift(mid, self.vf_prev_mid)
        self.vf_prev_mid = mid

        # Whale signal — bullish bias on VF when Mark 49/22 SELL VF or Mark 67 BUY VF.
        # Mean +$2-3 in 50 ticks on R4_d1/d2; weaker on R4_d3. Disabled on hard days.
        if not hasattr(self, '_whale_signal'): self._whale_signal = 0
        if self._whale_signal > 0: self._whale_signal -= 1
        if not hasattr(self, '_m67_signal'): self._m67_signal = 0
        if self._m67_signal > 0: self._m67_signal -= 1
        whale_just_fired = False
        for t in state.market_trades.get(prod, []):
            if (t.seller == 'Mark 49'
                    or t.buyer == 'Mark 67'
                    or (self.WHALE_INCLUDE_MARK_22 and t.seller == 'Mark 22')):
                self._whale_signal = self.WHALE_TICKS
                whale_just_fired = True
            if t.buyer == 'Mark 67':
                self._m67_signal = self.AGGRO_M67_TICKS
        self._whale_just_fired = whale_just_fired
        # Skip whale on hard day (signal weakens, hurts R4_d3 MIN)
        whale_active = self._whale_signal > 0 and not (
            self.ENABLE_DAY_DETECT and self._is_hard_day)
        whale_bias = self.WHALE_BIAS if whale_active else 0.0

        # Dynamic VF anchor (blend with rolling)
        if not hasattr(self, '_vf_anchor_buf'): self._vf_anchor_buf = []
        if self.VF_DYNAMIC_BLEND > 0:
            self._vf_anchor_buf.append(mid)
            if len(self._vf_anchor_buf) > self.DYN_ANCHOR_WINDOW:
                del self._vf_anchor_buf[:len(self._vf_anchor_buf) - self.DYN_ANCHOR_WINDOW]
            roll = sum(self._vf_anchor_buf) / len(self._vf_anchor_buf)
            vf_anchor = (1.0 - self.VF_DYNAMIC_BLEND) * self._vf_active_anchor + self.VF_DYNAMIC_BLEND * roll
        else:
            vf_anchor = self._vf_active_anchor
        fair = vf_anchor + self.VF_IMBAL_SHIFT * imbal + shock + whale_bias
        n = len(self.vf_mids)
        eff_edge = self.vf_edge * self.WARMUP_EDGE_MULT if n < self.WARMUP_TICKS else self.vf_edge
        pos = state.position.get(prod, 0)
        fair_skewed = fair - self.vf_inv_skew * pos
        hard = self.POS_LIMIT[prod]
        order_list = []
        buy_room = hard - pos; sell_room = hard + pos
        # WHALE FORCE-TAKE: on the EVENT TICK only (not duration), buy aggressively
        # at the ask. Bypasses the edge filter. Fires on whale prints (Mark 49 sell
        # / Mark 67 buy / Mark 22 sell). Disabled on hard day.
        if (self.WHALE_FORCE_TAKE and whale_just_fired and whale_active
                and pos < self.vf_soft_cap):
            cap_room = min(buy_room, self.vf_soft_cap - pos + 30)
            qty = min(best_ask_vol, cap_room, self.WHALE_FORCE_QTY)
            if qty > 0:
                order_list.append(Order(prod, best_ask, qty))
                buy_room -= qty
        if best_ask < fair_skewed - eff_edge and pos < self.vf_soft_cap:
            cap_room = min(buy_room, self.vf_soft_cap - pos + 30)
            qty = min(best_ask_vol, cap_room, self.vf_take_clip)
            if qty > 0: order_list.append(Order(prod, best_ask, qty)); buy_room -= qty
        if best_bid > fair_skewed + eff_edge and pos > -self.vf_soft_cap:
            cap_room = min(sell_room, self.vf_soft_cap + pos + 30)
            qty = min(best_bid_vol, cap_room, self.vf_take_clip)
            if qty > 0: order_list.append(Order(prod, best_bid, -qty)); sell_room -= qty
        if n >= self.WARMUP_TICKS:
            order_list.extend(self._ladder_makes(prod, best_bid, best_ask, fair_skewed, buy_room, sell_room))
        if order_list: orders[prod] = order_list

    def _vf_S(self, state) -> Optional[float]:
        od = state.order_depths.get('VELVETFRUIT_EXTRACT')
        if od is None or not od.buy_orders or not od.sell_orders:
            return None
        return (max(od.buy_orders.keys()) + min(od.sell_orders.keys())) / 2.0

    def _build_smile(self, state, S: float, T: float) -> Optional[Tuple[float, float, float]]:
        """Fit IV(m_t) parabola across SMILE_FIT_STRIKES. Returns (a,b,c) or None."""
        if S is None or T <= 0: return None
        ms: List[float] = []
        ivs: List[float] = []
        sqT = sqrt(T)
        for sym, K in self.SMILE_FIT_STRIKES.items():
            if sym not in state.order_depths: continue
            od = state.order_depths[sym]
            if not od.buy_orders or not od.sell_orders: continue
            mid = (max(od.buy_orders.keys()) + min(od.sell_orders.keys())) / 2.0
            iv = implied_vol(mid, S, K, T)
            if iv is None: continue
            if iv < self.SMILE_MIN_IV or iv > self.SMILE_MAX_IV: continue
            ms.append(log(K / S) / sqT)
            ivs.append(iv)
        if len(ms) < self.SMILE_MIN_POINTS:
            return None
        return fit_quadratic(ms, ivs)

    def _smile_voucher_mr(self, state, orders: Dict[str, List[Order]]):
        """v77_r4-style rolling-mean MR + small additive smile bias.

        Each strike:
          rolling_fair = mean of past mids
          smile_fair = BS(S, K, T, σ_from_parabola) if smile fittable & in range
          fair = rolling_fair + clamp(SMILE_BIAS_W * (smile_fair - rolling_fair),
                                       ±SMILE_BIAS_CAP)
          (SMILE_BIAS_W=0 reproduces v77_r4 exactly.)
        """
        S = self._vf_S(state)
        T = self._time_to_expiry(state.timestamp)
        smile = self._build_smile(state, S, T)
        sqT = sqrt(T) if T > 0 else 1e-3
        for sym, K in self.TRADE_STRIKES.items():
            if sym not in state.order_depths: continue
            od = state.order_depths[sym]
            if not od.buy_orders or not od.sell_orders: continue
            best_bid = max(od.buy_orders.keys()); best_ask = min(od.sell_orders.keys())
            best_bid_vol = od.buy_orders[best_bid]; best_ask_vol = abs(od.sell_orders[best_ask])
            mid = (best_bid + best_ask) / 2.0
            # rolling history
            if sym not in self.opt_mids: self.opt_mids[sym] = []
            self.opt_mids[sym].append(mid)
            if len(self.opt_mids[sym]) > self.opt_window:
                self.opt_mids[sym] = self.opt_mids[sym][-self.opt_window:]
            if len(self.opt_mids[sym]) < 20: continue
            rolling_fair = sum(self.opt_mids[sym]) / len(self.opt_mids[sym])

            # Compute smile bias: smile_fair - current_mid is the cross-sectional
            # residual (positive = option cheap vs smile → buy; negative = rich → sell).
            bias = 0.0
            if S is not None and S > 0 and T > 0:
                sigma_smile = None
                if self.SMILE_MODE == 'parabola' and smile is not None:
                    a, b, c = smile
                    m_K = log(K / S) / sqT
                    # Day-aware m_range
                    m_range = self.SMILE_BIAS_M_RANGE
                    if (self.ENABLE_DAY_DETECT and self._is_hard_day
                            and self.HARD_DAY_SMILE_M_RANGE is not None):
                        m_range = self.HARD_DAY_SMILE_M_RANGE
                    if abs(m_K) <= m_range:
                        sigma_cand = a * m_K * m_K + b * m_K + c
                        if self.SMILE_MIN_IV <= sigma_cand <= self.SMILE_MAX_IV:
                            sigma_smile = sigma_cand
                elif self.SMILE_MODE == 'static':
                    sigma_smile = self.STATIC_IV.get(sym)
                if sigma_smile is not None:
                    # Day-aware EMA smoothing of smile-IV
                    ema_a = self.SMILE_IV_EMA_ALPHA
                    if (self.ENABLE_DAY_DETECT and self._is_hard_day
                            and self.HARD_DAY_SMILE_IV_EMA is not None):
                        ema_a = self.HARD_DAY_SMILE_IV_EMA
                    if ema_a > 0:
                        prev = self._smile_iv_ema.get(sym, sigma_smile)
                        sigma_used = ema_a * sigma_smile + (1 - ema_a) * prev
                        self._smile_iv_ema[sym] = sigma_used
                    else:
                        sigma_used = sigma_smile
                    smile_fair = bs_call(S, K, T, sigma_used)
                    # Day-aware smile bias weight & cap
                    if (self.ENABLE_DAY_DETECT and self._is_hard_day
                            and self.HARD_DAY_SMILE_BIAS_W is not None):
                        w_use = self.HARD_DAY_SMILE_BIAS_W
                        cap_use = (self.HARD_DAY_SMILE_BIAS_CAP
                                   if self.HARD_DAY_SMILE_BIAS_CAP is not None
                                   else self.SMILE_BIAS_CAP)
                    else:
                        w_use = self.SMILE_BIAS_W
                        cap_use = self.SMILE_BIAS_CAP
                    raw_bias = w_use * (smile_fair - mid)
                    bias = max(-cap_use, min(cap_use, raw_bias))

            fair = rolling_fair + bias
            pos = state.position.get(sym, 0)
            # Day-aware skew: harder skew on hard days (R4_d3-like)
            hard = self.ENABLE_DAY_DETECT and self._is_hard_day
            soft_high = (self.ENABLE_SOFT_HIGH_VF_DETECT and self._is_soft_high_vf
                         and self.SOFT_HIGH_VF_OPT_INV_SKEW is not None)
            if hard:
                inv_skew = self.HARD_DAY_OPT_INV_SKEW
            elif soft_high:
                inv_skew = self.SOFT_HIGH_VF_OPT_INV_SKEW
            else:
                inv_skew = self.opt_inv_skew
            fair_skewed = fair - inv_skew * pos
            edge = self.opt_edge_v77
            # Per-strike clip override; per-day-type overrides take precedence
            if self.USE_OPT_CLIP_MAP:
                if hard and sym in self.HARD_DAY_CLIP_OVERRIDES:
                    take_clip = self.HARD_DAY_CLIP_OVERRIDES[sym]
                elif (self.ENABLE_SOFT_HIGH_VF_DETECT and self._is_soft_high_vf
                      and sym in self.SOFT_HIGH_VF_CLIP_OVERRIDES):
                    take_clip = self.SOFT_HIGH_VF_CLIP_OVERRIDES[sym]
                else:
                    take_clip = self.OPT_CLIP_MAP.get(sym, self.opt_take_clip_v77)
            else:
                take_clip = self.opt_take_clip_v77
            order_list: List[Order] = []
            if best_ask < fair_skewed - edge and pos < self.opt_soft_cap:
                room = min(self.OPT_LIMIT - pos, self.opt_soft_cap - pos + 15)
                qty = min(best_ask_vol, room, take_clip)
                if qty > 0: order_list.append(Order(sym, best_ask, qty))
            if best_bid > fair_skewed + edge and pos > -self.opt_soft_cap:
                room = min(self.OPT_LIMIT + pos, self.opt_soft_cap + pos + 15)
                qty = min(best_bid_vol, room, take_clip)
                if qty > 0: order_list.append(Order(sym, best_bid, -qty))
            if order_list: orders.setdefault(sym, []).extend(order_list)

    def _delta_hedge(self, state, orders: Dict[str, List[Order]]):
        """Hedge net option delta with VF (additive to VF MR)."""
        S = self._vf_S(state)
        T = self._time_to_expiry(state.timestamp)
        if S is None or T <= 0: return
        smile = self._build_smile(state, S, T)
        if smile is None: return
        a, b, c = smile
        sqT = sqrt(T)

        net_delta = 0.0
        for sym, K in self.HEDGE_STRIKES.items():
            pos = state.position.get(sym, 0)
            if pos == 0: continue
            m_K = log(K / S) / sqT
            sigma_smile = a * m_K * m_K + b * m_K + c
            if not (self.SMILE_MIN_IV <= sigma_smile <= self.SMILE_MAX_IV):
                continue
            d = bs_call_delta(S, K, T, sigma_smile)
            net_delta += pos * d

        target_vf = -int(round(net_delta))
        # Reserve some VF capacity for MR; cap hedge at HEDGE_VF_RESERVE
        target_vf = max(-self.HEDGE_VF_RESERVE, min(self.HEDGE_VF_RESERVE, target_vf))
        cur_vf = state.position.get('VELVETFRUIT_EXTRACT', 0)
        diff = target_vf - cur_vf
        if abs(diff) < self.HEDGE_THRESHOLD: return

        vf_od = state.order_depths.get('VELVETFRUIT_EXTRACT')
        if vf_od is None or not vf_od.buy_orders or not vf_od.sell_orders: return
        vf_bid = max(vf_od.buy_orders.keys()); vf_ask = min(vf_od.sell_orders.keys())
        vf_hard = self.POS_LIMIT['VELVETFRUIT_EXTRACT']
        if diff > 0:
            room = vf_hard - cur_vf
            qty = min(diff, abs(vf_od.sell_orders[vf_ask]), room, 30)
            if qty > 0:
                orders.setdefault('VELVETFRUIT_EXTRACT', []).append(
                    Order('VELVETFRUIT_EXTRACT', vf_ask, qty))
        else:
            room = vf_hard + cur_vf
            qty = min(-diff, vf_od.buy_orders[vf_bid], room, 30)
            if qty > 0:
                orders.setdefault('VELVETFRUIT_EXTRACT', []).append(
                    Order('VELVETFRUIT_EXTRACT', vf_bid, -qty))
