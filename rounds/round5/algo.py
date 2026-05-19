"""
r5_smooth_v1 — TEMPLATE (placeholder).

Built from per_pair_attribution.json with --ratio=4.0.
Heroes: 39  D4_DEPENDENT: 35  OTHER_DOMINANT: 7  WEAK: 2  LOSER: 4  MIXED: 13.
Pairs kept: 39.


Goal: per-day distribution closer to $300k/$300k/$400k by:
  - Keeping ONLY the HEROES from Phase 1 (positive on all 3 days, ratio<4×)
  - Keeping the MICROCHIP triplet (verified real signal)
  - Optionally adding per-family alt signals from Phase 2 if they beat pair_mr

Promotion criteria (BOTH):
  - per-day best/worst < 2.5×
  - pooled total > $800k

If first attempt fails: try ratio thresholds 3×, 2×; add D4_DEPENDENT at 50% size.
"""
from __future__ import annotations
import json
from typing import Dict, List

try:
    from datamodel import Order  # noqa: F401
except ModuleNotFoundError:
    Order = None


PAIR_SEEDS = {
    # MICROCHIP
    "MICROCHIP_SQUARE|MICROCHIP_TRIANGLE": (6317.9, 538.6),
    "MICROCHIP_RECTANGLE|MICROCHIP_SQUARE": (-6624.5, 693.0),
    "MICROCHIP_OVAL|MICROCHIP_SQUARE": (-8702.9, 514.0),
    "MICROCHIP_OVAL|MICROCHIP_TRIANGLE": (-2385.0, 248.2),
    # ROBOT
    "ROBOT_DISHES|ROBOT_MOPPING": (-1111.9, 540.3),
    "ROBOT_IRONING|ROBOT_VACUUMING": (-770.3, 263.7),
    # OXYGEN_SHAKE
    "OXYGEN_SHAKE_CHOCOLATE|OXYGEN_SHAKE_GARLIC": (-2839.6, 310.4),
    "OXYGEN_SHAKE_GARLIC|OXYGEN_SHAKE_MORNING_BREATH": (3404.9, 729.2),
    "OXYGEN_SHAKE_MINT|OXYGEN_SHAKE_MORNING_BREATH": (-150.4, 609.7),
    # UV_VISOR
    "UV_VISOR_AMBER|UV_VISOR_RED": (-4903.2, 401.8),
    "UV_VISOR_AMBER|UV_VISOR_MAGENTA": (-4693.1, 324.1),
    # PEBBLES
    "PEBBLES_M|PEBBLES_XS": (4815.7, 573.3),
    "PEBBLES_S|PEBBLES_XS": (1893.1, 367.6),
    "PEBBLES_L|PEBBLES_XS": (4402.0, 670.4),
    "PEBBLES_L|PEBBLES_S": (2509.0, 518.0),
    # SNACKPACK
    "SNACKPACK_CHOCOLATE|SNACKPACK_VANILLA": (-533.0, 343.8),
    "SNACKPACK_PISTACHIO|SNACKPACK_RASPBERRY": (-706.6, 302.6),
    "SNACKPACK_CHOCOLATE|SNACKPACK_STRAWBERRY": (-1361.3, 285.7),
    "SNACKPACK_RASPBERRY|SNACKPACK_VANILLA": (-150.4, 228.4),
    "SNACKPACK_CHOCOLATE|SNACKPACK_RASPBERRY": (-382.5, 252.1),
    "SNACKPACK_CHOCOLATE|SNACKPACK_PISTACHIO": (323.7, 217.7),
    "SNACKPACK_PISTACHIO|SNACKPACK_VANILLA": (-857.4, 230.3),
    "SNACKPACK_PISTACHIO|SNACKPACK_STRAWBERRY": (-1685.3, 124.1),
    # TRANSLATOR
    "TRANSLATOR_ECLIPSE_CHARCOAL|TRANSLATOR_SPACE_GRAY": (816.7, 424.8),
    "TRANSLATOR_ECLIPSE_CHARCOAL|TRANSLATOR_VOID_BLUE": (-1445.2, 417.9),
    "TRANSLATOR_ASTRO_BLACK|TRANSLATOR_VOID_BLUE": (-2046.6, 392.2),
    "TRANSLATOR_ASTRO_BLACK|TRANSLATOR_ECLIPSE_CHARCOAL": (-601.4, 222.6),
    # SLEEP_POD
    "SLEEP_POD_COTTON|SLEEP_POD_POLYESTER": (-311.9, 381.4),
    "SLEEP_POD_POLYESTER|SLEEP_POD_SUEDE": (771.4, 363.5),
    "SLEEP_POD_LAMB_WOOL|SLEEP_POD_SUEDE": (-1179.0, 422.1),
    "SLEEP_POD_COTTON|SLEEP_POD_SUEDE": (459.5, 586.8),
    "SLEEP_POD_LAMB_WOOL|SLEEP_POD_NYLON": (685.3, 348.5),
    "SLEEP_POD_COTTON|SLEEP_POD_LAMB_WOOL": (1638.5, 779.1),
    # GALAXY_SOUNDS
    "GALAXY_SOUNDS_DARK_MATTER|GALAXY_SOUNDS_SOLAR_FLAMES": (-776.0, 581.6),
    "GALAXY_SOUNDS_PLANETARY_RINGS|GALAXY_SOUNDS_SOLAR_FLAMES": (-250.6, 445.2),
    "GALAXY_SOUNDS_DARK_MATTER|GALAXY_SOUNDS_PLANETARY_RINGS": (-525.4, 456.9),
    "GALAXY_SOUNDS_BLACK_HOLES|GALAXY_SOUNDS_SOLAR_WINDS": (1676.0, 674.6),
    # PANEL
    "PANEL_1X2|PANEL_2X4": (-2620.0, 231.8),
    "PANEL_1X4|PANEL_2X2": (-218.1, 193.1),
}

# MICROCHIP cointegrated triplet — kept (real signal verified)
TRIPLET_SEEDS = [
    ('MICROCHIP_TRIANGLE', 'MICROCHIP_OVAL', 'MICROCHIP_RECTANGLE', 8583.4, 0.607, -0.443, 0.0, 323.5),
]


def _mid(d):
    if not d.buy_orders or not d.sell_orders:
        return None
    return (max(d.buy_orders) + min(d.sell_orders)) / 2.0


def _bb_ba(d):
    bb = max(d.buy_orders) if d.buy_orders else None
    ba = min(d.sell_orders) if d.sell_orders else None
    return bb, ba


class Trader:
    POS_LIMIT = 10
    PAIR_MAX_POS = 10
    PAIR_ENTER_Z = 1.70
    PAIR_EXIT_Z = 0.0
    EMA_ALPHA = 0.0002
    VAR_ALPHA = 0.0002
    WARMUP_TICKS = 0
    DEFAULT_INIT_VAR = 1_000_000.0
    TRIPLET_MAX_POS = 2
    TRIPLET_HEDGE_CAP = 4
    TRIPLET_ENTER_Z = 1.70
    TRIPLET_EXIT_Z = 0.0

    def _state(self, td):
        if not td:
            return {"em": {}, "ev": {}, "tick": 0}
        try:
            return json.loads(td)
        except Exception:
            return {"em": {}, "ev": {}, "tick": 0}

    def _ema(self, st, key, x, mean_seed=None, std_seed=None):
        m = st["em"].get(key)
        if m is None:
            init_mean = mean_seed if mean_seed is not None else x
            init_var = (std_seed * std_seed) if std_seed else self.DEFAULT_INIT_VAR
            st["em"][key] = init_mean
            st["ev"][key] = init_var
            return init_mean, init_var
        m2 = m + self.EMA_ALPHA * (x - m)
        v_prev = st["ev"].get(key, self.DEFAULT_INIT_VAR)
        v_new = (1 - self.VAR_ALPHA) * v_prev + self.VAR_ALPHA * (x - m) ** 2
        st["em"][key] = m2
        st["ev"][key] = v_new
        return m2, v_new

    def _trade_pair(self, st, depths, leg_a, leg_b, max_pos, targets):
        da = depths.get(leg_a); db = depths.get(leg_b)
        if da is None or db is None: return
        ma = _mid(da); mb = _mid(db)
        if ma is None or mb is None: return
        spread = ma - mb
        seed = PAIR_SEEDS.get(f"{leg_a}|{leg_b}")
        m, v = self._ema(st, f"{leg_a}|{leg_b}", spread,
                         mean_seed=seed[0] if seed else None,
                         std_seed=seed[1] if seed else None)
        if st["tick"] < self.WARMUP_TICKS: return
        std = max(v ** 0.5, 1.0)
        z = (spread - m) / std
        if z > self.PAIR_ENTER_Z:
            targets[leg_a] = targets.get(leg_a, 0) - max_pos
            targets[leg_b] = targets.get(leg_b, 0) + max_pos
        elif z < -self.PAIR_ENTER_Z:
            targets[leg_a] = targets.get(leg_a, 0) + max_pos
            targets[leg_b] = targets.get(leg_b, 0) - max_pos
        elif abs(z) < self.PAIR_EXIT_Z:
            targets[leg_a] = 0
            targets[leg_b] = 0

    def _trade_triplet(self, st, depths, y_leg, x1_leg, x2_leg,
                       alpha, beta1, beta2, mean_seed, std_seed, targets):
        dy = depths.get(y_leg); d1 = depths.get(x1_leg); d2 = depths.get(x2_leg)
        if dy is None or d1 is None or d2 is None: return
        my = _mid(dy); m1 = _mid(d1); m2 = _mid(d2)
        if my is None or m1 is None or m2 is None: return
        spread = my - beta1 * m1 - beta2 * m2 - alpha
        key = f"T:{y_leg}|{x1_leg}|{x2_leg}"
        m, v = self._ema(st, key, spread,
                         mean_seed=mean_seed, std_seed=std_seed)
        if st["tick"] < self.WARMUP_TICKS: return
        std = max(v ** 0.5, 1.0)
        z = (spread - m) / std
        h1 = max(-self.TRIPLET_HEDGE_CAP,
                 min(self.TRIPLET_HEDGE_CAP, int(round(beta1 * self.TRIPLET_MAX_POS))))
        h2 = max(-self.TRIPLET_HEDGE_CAP,
                 min(self.TRIPLET_HEDGE_CAP, int(round(beta2 * self.TRIPLET_MAX_POS))))
        if z > self.TRIPLET_ENTER_Z:
            targets[y_leg] = targets.get(y_leg, 0) - self.TRIPLET_MAX_POS
            targets[x1_leg] = targets.get(x1_leg, 0) + h1
            targets[x2_leg] = targets.get(x2_leg, 0) + h2
        elif z < -self.TRIPLET_ENTER_Z:
            targets[y_leg] = targets.get(y_leg, 0) + self.TRIPLET_MAX_POS
            targets[x1_leg] = targets.get(x1_leg, 0) - h1
            targets[x2_leg] = targets.get(x2_leg, 0) - h2

    def _emit(self, depths, positions, targets):
        out: Dict[str, List[Order]] = {}
        for leg, raw in targets.items():
            target = max(-self.POS_LIMIT, min(self.POS_LIMIT, raw))
            cur = positions.get(leg, 0)
            delta = target - cur
            if delta == 0: continue
            d = depths.get(leg)
            if d is None: continue
            bb, ba = _bb_ba(d)
            if delta > 0 and ba is not None:
                out.setdefault(leg, []).append(Order(leg, ba, delta))
            elif delta < 0 and bb is not None:
                out.setdefault(leg, []).append(Order(leg, bb, delta))
        return out

    def run(self, state):
        st = self._state(state.traderData)
        st["tick"] = st.get("tick", 0) + 1
        depths = state.order_depths
        positions = state.position
        targets: Dict[str, int] = {}

        for key in PAIR_SEEDS:
            la, lb = key.split("|")
            self._trade_pair(st, depths, la, lb, self.PAIR_MAX_POS, targets)

        for y_leg, x1, x2, alpha, b1, b2, mu, sd in TRIPLET_SEEDS:
            self._trade_triplet(st, depths, y_leg, x1, x2,
                                alpha, b1, b2, mu, sd, targets)

        out = self._emit(depths, positions, targets)
        return out, 0, json.dumps(st)
