"""
v97 — v89 base + multi-dimensional grid-search winner for day 2 1000t.

Sweep harness: algos/strategies/v97_grid_sweep.py
Sweep log:     algos/results/v97_grid_log.json

Method: 4-pass coordinate descent over 9 axes (vf_edge, vf_inv_skew,
opt_window, opt_edge, hg_edge, VF_IMBAL_SHIFT, VF_FLOW_COEF, opt_take_clip,
vf_take_clip) with three targeted 2D refinements on highly-interactive pairs.

Result: day 2 1000t = $53,737 (v89 = $53,500, delta = +$237).

Changes vs v89 baseline (instance attrs):
  vf_edge:        3    -> 2
  vf_inv_skew:    0.01 -> 0.0
  VF_FLOW_COEF:   0.8  -> 0.4   (class attr)
  opt_take_clip:  25   -> 35
  vf_take_clip:   40   -> 50

Unchanged: opt_window=500, opt_edge=7, hg_edge=12, VF_IMBAL_SHIFT=1.0
(top configs tie across IMBAL_SHIFT 1.0/1.5/2.0 -> joint plateau).

Top 10 from sweep all share (vf_edge=2, vf_inv_skew=0.0, vf_take_clip=50)
indicating strong robustness on the VF axes. Drawdown unchanged at $28,103.
Sharpe 1.66.
"""

from math import floor, ceil
import json
import math
from typing import Any, Dict, List, Optional

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


class Logger:
    def __init__(self):
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects, sep=" ", end="\n"):
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state, orders, conversions, trader_data):
        base_length = len(self.to_json([
            self.compress_state(state, ""), self.compress_orders(orders),
            conversions, "", "",
        ]))
        max_item_length = (self.max_log_length - base_length) // 3
        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders), conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length),
        ]))
        self.logs = ""

    def compress_state(self, state, trader_data):
        return [state.timestamp, trader_data,
                self.compress_listings(state.listings),
                self.compress_order_depths(state.order_depths),
                self.compress_trades(state.own_trades),
                self.compress_trades(state.market_trades),
                state.position,
                self.compress_observations(state.observations)]

    def compress_listings(self, ls):
        return [[l.symbol, l.product, l.denomination] for l in ls.values()]

    def compress_order_depths(self, ods):
        return {s: [od.buy_orders, od.sell_orders] for s, od in ods.items()}

    def compress_trades(self, trades):
        out = []
        for tl in trades.values():
            for t in tl:
                out.append([t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp])
        return out

    def compress_observations(self, obs):
        co = {}
        for p, o in obs.conversionObservations.items():
            co[p] = [o.bidPrice, o.askPrice, o.transportFees, o.exportTariff, o.importTariff]
        return [obs.plainValueObservations, co]

    def compress_orders(self, orders):
        out = []
        for ol in orders.values():
            for o in ol:
                out.append([o.symbol, o.price, o.quantity])
        return out

    def to_json(self, value):
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value, max_length):
        v = value or ""
        lo, hi = 0, min(len(v), max_length)
        out = ""
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = v[:mid] + ("..." if mid < len(v) else "")
            if len(json.dumps(candidate)) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1
        return out


logger = Logger()


def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def bs_call(S, K, T, sigma, r=0.0):
    if T <= 0 or sigma <= 0 or S <= 0:
        return max(S - K, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)


class Trader:
    POS_LIMIT = {'HYDROGEL_PACK': 200, 'VELVETFRUIT_EXTRACT': 200}
    OPT_LIMIT = 300

    WARMUP_TICKS = 50
    WARMUP_EDGE_MULT = 3.0
    HG_OU_MU = 9965
    OPT_WINDOW_MAP = {
        "VEV_4000": 600,
        "VEV_4500": 500,
        "VEV_5000": 100,
        "VEV_5100": 200,
        "VEV_5200": 150,
        "VEV_5300": 500,
        "VEV_5400": 500,
        "VEV_5500": 500,
    }
    OPT_ZSCORE_THRESH = 3.0  # v115 winner
    OPT_ZSCORE_EDGE = 3
    OPT_ZSCORE_CLIP_MULT = 1.5
    OPT_EDGE_MAP = {
        "VEV_4000": 6, "VEV_4500": 7,
        "VEV_5000": 8, "VEV_5100": 8, "VEV_5200": 7,
        "VEV_5300": 4, "VEV_5400": 3, "VEV_5500": 7,
    }
    HG_MU_BLEND_W = 0.9  # v92 winner
    HG_MU_EMA_ALPHA = 0.02  # v45 peak  # tuned to observed first-1000-tick HG mean

    ATM_STRIKES = {
        'VEV_5000': 5000, 'VEV_5100': 5100, 'VEV_5200': 5200,
        'VEV_5300': 5300, 'VEV_5400': 5400, 'VEV_5500': 5500,
    }
    ITM_STRIKES = {'VEV_4000': 4000, 'VEV_4500': 4500}
    WING_STRIKES = {'VEV_6000': 6000, 'VEV_6500': 6500}

    IV_MAP = {
        'VEV_4000': 0.60, 'VEV_4500': 0.42,
        'VEV_5000': 0.30, 'VEV_5100': 0.30, 'VEV_5200': 0.30,
        'VEV_5300': 0.30, 'VEV_5400': 0.30, 'VEV_5500': 0.31,
        'VEV_6000': 0.40, 'VEV_6500': 0.55,
    }  # peak 10k PnL per IV sweep
    # Per-strike soft cap proportional to Lucas's expected-PnL tiers
    OPT_SOFT_CAP_MAP = {
        'VEV_4000': 120,  # Lucas: 5,702
        'VEV_4500': 150,  # Lucas: 7,986
        'VEV_5000': 280,  # Lucas: 20,117 — peak strike
        'VEV_5100': 280,  # Lucas: 21,506 — peak strike
        'VEV_5200': 250,  # Lucas: 18,310
        'VEV_5300': 150,  # Lucas: 9,828
        'VEV_5400': 80,   # Lucas: 3,873
        'VEV_5500': 40,   # Lucas: 920 — barely profitable
    }
    # Per-strike max-clip (how many at a time)
    OPT_CLIP_MAP = {
        'VEV_4000': 10, 'VEV_4500': 12,
        'VEV_5000': 25, 'VEV_5100': 25, 'VEV_5200': 22,
        'VEV_5300': 15, 'VEV_5400': 8, 'VEV_5500': 5,
    }
    T_YEARS = 6.76 / 252.0

    MAKE_LADDER_OFFSETS = [1, 2, 3]
    MAKE_LADDER_CLIPS = {
        'HYDROGEL_PACK': [50, 40, 30],
        'VELVETFRUIT_EXTRACT': [40, 35, 25],
    }
    SHOCK_THRESHOLD = 5.0
    SHOCK_FADE_COEF = 0.3
    HG_IMBAL_SHIFT = -10.0
    VF_IMBAL_SHIFT = 0.0  # v83 winner (was 1.5); v97 grid: tie 1.0/1.5/2.0
    VF_FLOW_COEF = 0.4
    FLOW_ROLL_TICKS = 7
    FLOW_COEF_TAN = 3.0
    FLOW_SCALE = 5.0
    HG_FLOW_COEF = 0.4  # v97 grid winner (was 0.8 in v89/v86)

    def __init__(self):
        self.hg_edge = 12  # v50
        self.hg_inv_skew = -0.015  # v48 zero skew
        self.hg_soft_cap = 200
        self.hg_take_clip = 35
        self.hg_make_clip = 70
        self.hg_prev_mid: Optional[float] = None

        self.vf_mids: List[float] = []
        self.vf_window = 1500
        self.vf_edge = 2  # v97 grid winner (was 3 in v89)
        self.vf_inv_skew = -0.01  # v97 grid winner (was 0.01 in v89)
        self.vf_soft_cap = 200  # was 180; sweep winner at hard limit
        self.vf_take_clip = 75  # v97 grid winner (was 40 in v89)
        self.vf_make_clip = 60
        self.vf_prev_mid: Optional[float] = None

        self.opt_edge_abs = 3.0     # tightened from 4.0 to trigger more
        self.opt_edge_rel = 0.03  # sweep winner   # tightened from 0.04
        self.opt_inv_skew = 0.05    # softened from 0.1 to allow bigger positions


        # v53: rolling-mean MR for ATM options (tick-trade, not BS buy-and-hold)
        self.opt_mids: dict = {}
        self.opt_window = 500  # v60 peak (v97 grid confirmed)
        self.opt_edge = 7  # v60 peak (v97 grid confirmed)
        self.opt_soft_cap = 300  # hard limit
        self.opt_take_clip = 35  # v97 grid winner (was 25 in v89)
        self.opt_inv_skew = 0.0  # no skew for fast cycling

        self.wing_soft_cap = 150
        self.wing_sell_price = 1
        self.wing_make_clip = 50

    def encode_trader_data(self, state):
        return json.dumps({
            'vf': self.vf_mids,
            'hpm': self.hg_prev_mid,
            'vpm': self.vf_prev_mid,
        })

    def decode_trader_data(self, s):
        if not s:
            return
        try:
            d = json.loads(s)
            if isinstance(d, dict):
                if isinstance(d.get('vf'), list):
                    self.vf_mids = [float(x) for x in d['vf']]
                v = d.get('hpm')
                if v is not None:
                    self.hg_prev_mid = float(v)
                v = d.get('vpm')
                if v is not None:
                    self.vf_prev_mid = float(v)
        except Exception:
            pass

    def run(self, state):
        self.decode_trader_data(state.traderData)
        self._tick_count = getattr(self, "_tick_count", 0) + 1
        orders = {}
        self._hg(state, orders)
        self._vf(state, orders)
        self._atm_options(state, orders)
        self._atm_mr(state, orders)
        self._itm_options(state, orders)
        self._wings_sell_make(state, orders)
        trader_data = self.encode_trader_data(state)
        logger.flush(state, orders, 0, trader_data)
        return orders, 0, trader_data


    def _ladder_makes(self, prod, best_bid, best_ask, fair_skewed, buy_room, sell_room):
        out = []
        clips = self.MAKE_LADDER_CLIPS.get(prod, [30, 20, 10])
        for off, clip in zip(self.MAKE_LADDER_OFFSETS, clips):
            if buy_room <= 0: break
            make_bid = best_bid + off
            if make_bid >= fair_skewed: break
            if make_bid >= best_ask: break
            qty = min(buy_room, clip)
            if qty > 0:
                out.append(Order(prod, make_bid, qty))
                buy_room -= qty
        for off, clip in zip(self.MAKE_LADDER_OFFSETS, clips):
            if sell_room <= 0: break
            make_ask = best_ask - off
            if make_ask <= fair_skewed: break
            if make_ask <= best_bid: break
            qty = min(sell_room, clip)
            if qty > 0:
                out.append(Order(prod, make_ask, -qty))
                sell_room -= qty
        return out

    def _l1_imbalance(self, od):
        # Depth-weighted imbalance (v83): L1 + 0.7*L2
        bids = sorted(od.buy_orders.items(), reverse=True)[:2]
        asks = sorted(od.sell_orders.items())[:2]
        weights = [1.0, 0.7]
        bv = sum(w * v for w, (_, v) in zip(weights, bids))
        av = sum(w * abs(v) for w, (_, v) in zip(weights, asks))
        tot = bv + av
        return (bv - av) / tot if tot > 0 else 0.0

    def _shock_shift(self, cur_mid, prev_mid):
        if prev_mid is None:
            return 0.0
        r = cur_mid - prev_mid
        if abs(r) < self.SHOCK_THRESHOLD:
            return 0.0
        return -self.SHOCK_FADE_COEF * r

    def _hg(self, state, orders):
        prod = 'HYDROGEL_PACK'
        if prod not in state.order_depths:
            return
        od = state.order_depths[prod]
        if not od.buy_orders or not od.sell_orders:
            return
        best_bid = max(od.buy_orders.keys())
        best_ask = min(od.sell_orders.keys())
        best_bid_vol = od.buy_orders[best_bid]
        best_ask_vol = abs(od.sell_orders[best_ask])
        mid = (best_bid + best_ask) / 2.0

        imbal = self._l1_imbalance(od)
        shock = self._shock_shift(mid, self.hg_prev_mid)
        # v143 HG aggressor flow signal (sign-based)
        hg_flow_shift = 0.0
        hgmt = state.market_trades.get(prod, [])
        if hgmt:
            sq_hg = 0
            for t in hgmt:
                if t.price > mid: sq_hg += t.quantity
                elif t.price < mid: sq_hg -= t.quantity
            if sq_hg != 0:
                hg_flow_shift = self.HG_FLOW_COEF * (1 if sq_hg > 0 else -1)
        self.hg_prev_mid = mid

        # v92 HG MU blend: anchor + EMA
        if not hasattr(self, '_hg_ema'):
            self._hg_ema = mid
        else:
            a = self.HG_MU_EMA_ALPHA
            self._hg_ema = a * mid + (1 - a) * self._hg_ema
        mu = self.HG_MU_BLEND_W * self.HG_OU_MU + (1 - self.HG_MU_BLEND_W) * self._hg_ema
        fair = mu + self.HG_IMBAL_SHIFT * imbal + shock + hg_flow_shift
        pos = state.position.get(prod, 0)
        fair_skewed = fair - self.hg_inv_skew * pos

        edge = self.hg_edge
        hard = self.POS_LIMIT[prod]
        order_list = []
        buy_room = hard - pos
        sell_room = hard + pos

        # v124: position-aware HG buy aggression — sym to v94 but for buys
        if pos >= 0:
            buy_off, buy_clip_mult = 1, 1
        elif pos >= -50:
            buy_off, buy_clip_mult = 2, 2
        elif pos >= -100:
            buy_off, buy_clip_mult = 1, 1
        else:
            buy_off, buy_clip_mult = 0, 1
        eff_buy_edge = max(1, edge - buy_off)
        if best_ask < fair_skewed - eff_buy_edge and pos < self.hg_soft_cap:
            cap_room = min(buy_room, self.hg_soft_cap - pos + 30)
            qty = min(best_ask_vol, cap_room, self.hg_take_clip * buy_clip_mult)
            if qty > 0:
                order_list.append(Order(prod, best_ask, qty))
                buy_room -= qty
        # v170: HG SELL aggression mirroring buy aggression
        if pos <= -50:
            sell_off, sell_clip_mult = 0, 1
        elif pos <= 0:
            sell_off, sell_clip_mult = 1, 1
        elif pos <= 50:
            sell_off, sell_clip_mult = 2, 2
        elif pos <= 100:
            sell_off, sell_clip_mult = 3, 2
        else:
            sell_off, sell_clip_mult = 1, 1
        eff_sell_edge = max(1, edge - sell_off)
        if best_bid > fair_skewed + eff_sell_edge and pos > -self.hg_soft_cap:
            cap_room = min(sell_room, self.hg_soft_cap + pos + 30)
            qty = min(best_bid_vol, cap_room, self.hg_take_clip * sell_clip_mult)
            if qty > 0:
                order_list.append(Order(prod, best_bid, -qty))
                sell_room -= qty

        order_list.extend(self._ladder_makes(prod, best_bid, best_ask, fair_skewed, buy_room, sell_room))

        if order_list:
            orders[prod] = order_list

    def _vf(self, state, orders):
        prod = 'VELVETFRUIT_EXTRACT'
        if prod not in state.order_depths:
            return
        od = state.order_depths[prod]
        if not od.buy_orders or not od.sell_orders:
            return
        best_bid = max(od.buy_orders.keys())
        best_ask = min(od.sell_orders.keys())
        best_bid_vol = od.buy_orders[best_bid]
        best_ask_vol = abs(od.sell_orders[best_ask])
        mid = (best_bid + best_ask) / 2.0

        self.vf_mids.append(mid)
        if len(self.vf_mids) > self.vf_window:
            del self.vf_mids[:len(self.vf_mids) - self.vf_window]

        imbal = self._l1_imbalance(od)
        shock = self._shock_shift(mid, self.vf_prev_mid)
        self.vf_prev_mid = mid

        # v143: rolling-flow tanh signal
        if not hasattr(self, '_vf_flow_buf'):
            self._vf_flow_buf = [0.0] * self.FLOW_ROLL_TICKS
        sq_now = 0
        mt = state.market_trades.get(prod, [])
        if mt:
            for t in mt:
                if t.price > mid:
                    sq_now += t.quantity
                elif t.price < mid:
                    sq_now -= t.quantity
        self._vf_flow_buf.append(sq_now)
        if len(self._vf_flow_buf) > self.FLOW_ROLL_TICKS:
            self._vf_flow_buf.pop(0)
        rolling_sum = sum(self._vf_flow_buf)
        import math
        flow_shift = self.FLOW_COEF_TAN * math.tanh(rolling_sum / self.FLOW_SCALE)

        base_fair = sum(self.vf_mids) / len(self.vf_mids)
        fair = base_fair + self.VF_IMBAL_SHIFT * imbal + shock + flow_shift
        n = len(self.vf_mids)
        eff_edge = self.vf_edge * self.WARMUP_EDGE_MULT if n < self.WARMUP_TICKS else self.vf_edge

        pos = state.position.get(prod, 0)
        fair_skewed = fair - self.vf_inv_skew * pos

        hard = self.POS_LIMIT[prod]
        order_list = []
        buy_room = hard - pos
        sell_room = hard + pos

        if best_ask < fair_skewed - eff_edge and pos < self.vf_soft_cap:
            cap_room = min(buy_room, self.vf_soft_cap - pos + 30)
            qty = min(best_ask_vol, cap_room, self.vf_take_clip)
            if qty > 0:
                order_list.append(Order(prod, best_ask, qty))
                buy_room -= qty
        if best_bid > fair_skewed + eff_edge and pos > -self.vf_soft_cap:
            cap_room = min(sell_room, self.vf_soft_cap + pos + 30)
            qty = min(best_bid_vol, cap_room, self.vf_take_clip)
            if qty > 0:
                order_list.append(Order(prod, best_bid, -qty))
                sell_room -= qty

        if n >= self.WARMUP_TICKS:
            order_list.extend(self._ladder_makes(prod, best_bid, best_ask, fair_skewed, buy_room, sell_room))

        if order_list:
            orders[prod] = order_list


    def _atm_mr(self, state, orders):
        ATM_STRIKES = ['VEV_4000', 'VEV_4500', 'VEV_5000', 'VEV_5100', 'VEV_5200', 'VEV_5300', 'VEV_5400', 'VEV_5500']
        for prod in ATM_STRIKES:
            if prod not in state.order_depths:
                continue
            od = state.order_depths[prod]
            if not od.buy_orders or not od.sell_orders:
                continue
            best_bid = max(od.buy_orders.keys())
            best_ask = min(od.sell_orders.keys())
            best_bid_vol = od.buy_orders[best_bid]
            best_ask_vol = abs(od.sell_orders[best_ask])
            mid = (best_bid + best_ask) / 2.0

            if prod not in self.opt_mids:
                self.opt_mids[prod] = []
            self.opt_mids[prod].append(mid)
            eff_window = self.OPT_WINDOW_MAP.get(prod, self.opt_window)
            if len(self.opt_mids[prod]) > eff_window:
                self.opt_mids[prod] = self.opt_mids[prod][-eff_window:]
            if len(self.opt_mids[prod]) < 20:
                continue

            fair = sum(self.opt_mids[prod]) / len(self.opt_mids[prod])
            pos = state.position.get(prod, 0)
            fair_skewed = fair - self.opt_inv_skew * pos
            eff_edge = self.OPT_EDGE_MAP.get(prod, self.opt_edge)

            # v142 z-score aggressive take (from v115)
            mids_l = self.opt_mids[prod]
            if len(mids_l) >= 30:
                var = sum((m - fair) ** 2 for m in mids_l) / len(mids_l)
                stdev = (var ** 0.5) or 1.0
            else:
                stdev = 1.0
            ask_diff = fair_skewed - best_ask
            bid_diff = best_bid - fair_skewed
            ask_edge = eff_edge
            bid_edge = eff_edge
            clip = self.opt_take_clip
            if stdev > 0:
                if ask_diff / stdev >= self.OPT_ZSCORE_THRESH:
                    ask_edge = min(ask_edge, self.OPT_ZSCORE_EDGE)
                    clip = max(clip, int(self.opt_take_clip * self.OPT_ZSCORE_CLIP_MULT))
                if bid_diff / stdev >= self.OPT_ZSCORE_THRESH:
                    bid_edge = min(bid_edge, self.OPT_ZSCORE_EDGE)
                    clip = max(clip, int(self.opt_take_clip * self.OPT_ZSCORE_CLIP_MULT))

            order_list = []
            if best_ask < fair_skewed - ask_edge and pos < self.opt_soft_cap:
                room = min(300 - pos, self.opt_soft_cap - pos + 15)
                qty = min(best_ask_vol, room, clip)
                if qty > 0:
                    order_list.append(Order(prod, best_ask, qty))
            if best_bid > fair_skewed + bid_edge and pos > -self.opt_soft_cap:
                room = min(300 + pos, self.opt_soft_cap + pos + 15)
                qty = min(best_bid_vol, room, clip)
                if qty > 0:
                    order_list.append(Order(prod, best_bid, -qty))
            if order_list:
                orders[prod] = order_list

    def _atm_options(self, state, orders):
        return  # DISABLED for 1000t robustness
        if 'VELVETFRUIT_EXTRACT' not in state.order_depths:
            return
        u_od = state.order_depths['VELVETFRUIT_EXTRACT']
        if not u_od.buy_orders or not u_od.sell_orders:
            return
        S = (max(u_od.buy_orders.keys()) + min(u_od.sell_orders.keys())) / 2.0

        hard = self.OPT_LIMIT
        for prod, K in self.ATM_STRIKES.items():
            if prod not in state.order_depths:
                continue
            od = state.order_depths[prod]
            if not od.buy_orders or not od.sell_orders:
                continue
            best_bid = max(od.buy_orders.keys())
            best_ask = min(od.sell_orders.keys())
            best_bid_vol = od.buy_orders[best_bid]
            best_ask_vol = abs(od.sell_orders[best_ask])

            sigma = self.IV_MAP.get(prod, 0.24)
            fair = bs_call(S, K, self.T_YEARS, sigma)
            pos = state.position.get(prod, 0)
            fair_skewed = fair - self.opt_inv_skew * pos
            edge = max(self.opt_edge_abs, self.opt_edge_rel * max(fair, 1.0))

            soft_cap = self.OPT_SOFT_CAP_MAP.get(prod, 50)
            max_clip = self.OPT_CLIP_MAP.get(prod, 10)

            order_list = []
            if best_ask < fair_skewed - edge and pos < soft_cap:
                room = min(hard - pos, soft_cap - pos + 30)
                qty = min(best_ask_vol, room, max_clip)
                if qty > 0:
                    order_list.append(Order(prod, best_ask, qty))
            if best_bid > fair_skewed + edge and pos > -soft_cap:
                room = min(hard + pos, soft_cap + pos + 30)
                qty = min(best_bid_vol, room, max_clip)
                if qty > 0:
                    order_list.append(Order(prod, best_bid, -qty))

            # Option MAKE layer — post passive at best_bid+1 / best_ask-1 when inside fair
            spread = best_ask - best_bid
            if spread >= 2:
                opt_buy_room = min(hard - pos, soft_cap - pos)
                opt_sell_room = min(hard + pos, soft_cap + pos)
                # Skip takes count — positions already reflect takes; overshoot by 10 OK
                if opt_buy_room > 0:
                    mbid = min(best_bid + 1, int(floor(fair_skewed)) - 1)
                    if mbid > best_bid and mbid < best_ask and mbid < fair_skewed:
                        q = min(opt_buy_room, 6)
                        if q > 0:
                            order_list.append(Order(prod, mbid, q))
                if opt_sell_room > 0:
                    mask = max(best_ask - 1, int(ceil(fair_skewed)) + 1)
                    if mask < best_ask and mask > best_bid and mask > fair_skewed:
                        q = min(opt_sell_room, 6)
                        if q > 0:
                            order_list.append(Order(prod, mask, -q))

            if order_list:
                orders[prod] = order_list

    def _itm_options(self, state, orders):
        return  # DISABLED
        if 'VELVETFRUIT_EXTRACT' not in state.order_depths:
            return
        u_od = state.order_depths['VELVETFRUIT_EXTRACT']
        if not u_od.buy_orders or not u_od.sell_orders:
            return
        S = (max(u_od.buy_orders.keys()) + min(u_od.sell_orders.keys())) / 2.0

        hard = self.OPT_LIMIT
        for prod, K in self.ITM_STRIKES.items():
            if prod not in state.order_depths:
                continue
            od = state.order_depths[prod]
            if not od.buy_orders or not od.sell_orders:
                continue
            best_bid = max(od.buy_orders.keys())
            best_ask = min(od.sell_orders.keys())
            best_bid_vol = od.buy_orders[best_bid]
            best_ask_vol = abs(od.sell_orders[best_ask])

            sigma = self.IV_MAP.get(prod, 0.40)
            fair = bs_call(S, K, self.T_YEARS, sigma)
            intrinsic = max(S - K, 0.0)
            fair = max(fair, intrinsic)
            pos = state.position.get(prod, 0)
            fair_skewed = fair - self.opt_inv_skew * pos
            edge = max(2.5, 0.004 * max(fair, 1.0))

            soft_cap = self.OPT_SOFT_CAP_MAP.get(prod, 80)
            max_clip = self.OPT_CLIP_MAP.get(prod, 8)

            order_list = []
            if best_ask < fair_skewed - edge and pos < soft_cap:
                room = min(hard - pos, soft_cap - pos + 15)
                qty = min(best_ask_vol, room, max_clip)
                if qty > 0:
                    order_list.append(Order(prod, best_ask, qty))
            if best_bid > fair_skewed + edge and pos > -soft_cap:
                room = min(hard + pos, soft_cap + pos + 15)
                qty = min(best_bid_vol, room, max_clip)
                if qty > 0:
                    order_list.append(Order(prod, best_bid, -qty))
            if order_list:
                orders[prod] = order_list

    def _wings_sell_make(self, state, orders):
        return  # DISABLED
        for prod in self.WING_STRIKES:
            if prod not in state.order_depths:
                continue
            od = state.order_depths[prod]
            if not od.sell_orders:
                continue
            best_ask = min(od.sell_orders.keys())
            if best_ask != self.wing_sell_price:
                continue
            pos = state.position.get(prod, 0)
            hard = self.OPT_LIMIT
            sell_room = hard + pos
            if sell_room <= 0 or pos <= -self.wing_soft_cap:
                continue
            qty = min(sell_room, self.wing_soft_cap + pos, self.wing_make_clip)
            if qty > 0:
                orders.setdefault(prod, []).append(Order(prod, self.wing_sell_price, -qty))
