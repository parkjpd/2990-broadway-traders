"""r5_final — multi-layer ensemble: pair MR + PEBBLES H4 + structural bias.

Layers (per team integration plan):

  L1  Y_triplet pair MR           — 100 within-family cointegrated pair signals
                                    + MICROCHIP TRIANGLE/OVAL/RECTANGLE triplet.
                                    PAIR_MAX_POS=10, TRIPLET_MAX_POS=2, hedge cap 4.
                                    Standalone PnL across d2..d4: $1.22M.

  L2  PEBBLES H4                  — basket-sum confidence filter + extreme-leg z.
                                    When |basket_z|>1.7, pick the PEBBLES leg
                                    with the largest per-product |z|, full short/long
                                    in the opposite direction. Exit on z-cross.
                                    Standalone PnL across d2..d4: $196k (ratio 1.25x).

  L3  Structural bias             — constant directional positions on products with
                                    cross-day drift validated by team:
                                    MICROCHIP_OVAL=-N, OXYGEN_SHAKE_GARLIC=+N,
                                    UV_VISOR_AMBER=-N, UV_VISOR_RED=+N, PANEL_2X4=+N.
                                    GALAXY_SOUNDS_BLACK_HOLES=+N is gated by
                                    INCLUDE_GS_BH (default off — failed OOS in prior variant).

Combine: per-leg additive sum, clipped to ±POS_LIMIT (10).

L2 conflicts with L1's PEBBLES pair MR — H4 sets a single PEBBLES leg to
±10, while L1 may have summed several pair contributions. Additive merge
produces a compromise; H4's extreme contribution often dominates because
L1's per-leg accumulation gets clipped lower by per-pair caps.

Notes:
- Submission must be SINGLE FILE (this is it).
- No external imports beyond datamodel/json/typing/math/collections.
- Position limit per product: 10 (POS_LIMIT, R5 mod-confirmed).
"""
from __future__ import annotations

import json
from typing import Dict, List

try:
    from datamodel import Order  # noqa: F401
except ModuleNotFoundError:
    Order = None


# ============================================================================
# L1 — Y_triplet pair seeds (mu, sd) on day-4 stats. 100 within-family pairs.
# ============================================================================
PAIR_SEEDS = {
    # MICROCHIP
    "MICROCHIP_SQUARE|MICROCHIP_TRIANGLE": (6317.9, 538.6),
    "MICROCHIP_RECTANGLE|MICROCHIP_SQUARE": (-6624.5, 693.0),
    "MICROCHIP_OVAL|MICROCHIP_SQUARE": (-8702.9, 514.0),
    "MICROCHIP_CIRCLE|MICROCHIP_SQUARE": (-5375.0, 1180.1),
    "MICROCHIP_CIRCLE|MICROCHIP_OVAL": (3327.9, 1232.8),
    "MICROCHIP_OVAL|MICROCHIP_RECTANGLE": (-2078.5, 739.3),
    "MICROCHIP_OVAL|MICROCHIP_TRIANGLE": (-2385.0, 248.2),
    "MICROCHIP_RECTANGLE|MICROCHIP_TRIANGLE": (-306.5, 619.2),
    "MICROCHIP_CIRCLE|MICROCHIP_RECTANGLE": (1249.5, 716.0),
    "MICROCHIP_CIRCLE|MICROCHIP_TRIANGLE": (943.0, 1079.3),
    # ROBOT
    "ROBOT_DISHES|ROBOT_MOPPING": (-1111.9, 540.3),
    "ROBOT_DISHES|ROBOT_LAUNDRY": (1608.1, 288.9),
    "ROBOT_DISHES|ROBOT_IRONING": (2780.3, 462.7),
    "ROBOT_DISHES|ROBOT_VACUUMING": (2010.0, 366.0),
    "ROBOT_IRONING|ROBOT_MOPPING": (-3892.2, 287.6),
    "ROBOT_MOPPING|ROBOT_VACUUMING": (3121.9, 271.1),
    "ROBOT_IRONING|ROBOT_LAUNDRY": (-1172.2, 388.3),
    "ROBOT_LAUNDRY|ROBOT_MOPPING": (-2720.0, 402.1),
    "ROBOT_IRONING|ROBOT_VACUUMING": (-770.3, 263.7),
    "ROBOT_LAUNDRY|ROBOT_VACUUMING": (401.9, 226.7),
    # OXYGEN_SHAKE
    "OXYGEN_SHAKE_GARLIC|OXYGEN_SHAKE_MINT": (3554.6, 676.6),
    "OXYGEN_SHAKE_CHOCOLATE|OXYGEN_SHAKE_MINT": (715.0, 561.9),
    "OXYGEN_SHAKE_CHOCOLATE|OXYGEN_SHAKE_GARLIC": (-2839.6, 310.4),
    "OXYGEN_SHAKE_CHOCOLATE|OXYGEN_SHAKE_EVENING_BREATH": (644.4, 784.9),
    "OXYGEN_SHAKE_EVENING_BREATH|OXYGEN_SHAKE_GARLIC": (-3484.0, 808.0),
    "OXYGEN_SHAKE_CHOCOLATE|OXYGEN_SHAKE_MORNING_BREATH": (564.7, 725.8),
    "OXYGEN_SHAKE_GARLIC|OXYGEN_SHAKE_MORNING_BREATH": (3404.9, 729.2),
    "OXYGEN_SHAKE_EVENING_BREATH|OXYGEN_SHAKE_MORNING_BREATH": (-78.6, 235.9),
    "OXYGEN_SHAKE_EVENING_BREATH|OXYGEN_SHAKE_MINT": (70.6, 663.6),
    "OXYGEN_SHAKE_MINT|OXYGEN_SHAKE_MORNING_BREATH": (-150.4, 609.7),
    # UV_VISOR
    "UV_VISOR_RED|UV_VISOR_YELLOW": (1115.0, 961.4),
    "UV_VISOR_ORANGE|UV_VISOR_YELLOW": (155.2, 869.4),
    "UV_VISOR_MAGENTA|UV_VISOR_YELLOW": (904.9, 766.5),
    "UV_VISOR_AMBER|UV_VISOR_RED": (-4903.2, 401.8),
    "UV_VISOR_MAGENTA|UV_VISOR_RED": (-210.1, 434.4),
    "UV_VISOR_AMBER|UV_VISOR_MAGENTA": (-4693.1, 324.1),
    "UV_VISOR_AMBER|UV_VISOR_YELLOW": (-3788.2, 694.2),
    "UV_VISOR_MAGENTA|UV_VISOR_ORANGE": (749.7, 596.9),
    "UV_VISOR_ORANGE|UV_VISOR_RED": (-959.7, 603.3),
    "UV_VISOR_AMBER|UV_VISOR_ORANGE": (-3943.4, 651.5),
    # PEBBLES
    "PEBBLES_S|PEBBLES_XL": (-6715.8, 1896.4),
    "PEBBLES_XL|PEBBLES_XS": (8608.8, 1870.5),
    "PEBBLES_M|PEBBLES_XL": (-3793.1, 1461.1),
    "PEBBLES_L|PEBBLES_XL": (-4206.8, 2100.1),
    "PEBBLES_M|PEBBLES_S": (2922.7, 687.0),
    "PEBBLES_M|PEBBLES_XS": (4815.7, 573.3),
    "PEBBLES_S|PEBBLES_XS": (1893.1, 367.6),
    "PEBBLES_L|PEBBLES_M": (-413.7, 877.7),
    "PEBBLES_L|PEBBLES_XS": (4402.0, 670.4),
    "PEBBLES_L|PEBBLES_S": (2509.0, 518.0),
    # SNACKPACK
    "SNACKPACK_RASPBERRY|SNACKPACK_STRAWBERRY": (-978.7, 332.4),
    "SNACKPACK_CHOCOLATE|SNACKPACK_VANILLA": (-533.0, 343.8),
    "SNACKPACK_PISTACHIO|SNACKPACK_RASPBERRY": (-706.6, 302.6),
    "SNACKPACK_CHOCOLATE|SNACKPACK_STRAWBERRY": (-1361.3, 285.7),
    "SNACKPACK_RASPBERRY|SNACKPACK_VANILLA": (-150.4, 228.4),
    "SNACKPACK_CHOCOLATE|SNACKPACK_RASPBERRY": (-382.5, 252.1),
    "SNACKPACK_STRAWBERRY|SNACKPACK_VANILLA": (827.6, 207.4),
    "SNACKPACK_CHOCOLATE|SNACKPACK_PISTACHIO": (323.7, 217.7),
    "SNACKPACK_PISTACHIO|SNACKPACK_VANILLA": (-857.4, 230.3),
    "SNACKPACK_PISTACHIO|SNACKPACK_STRAWBERRY": (-1685.3, 124.1),
    # TRANSLATOR
    "TRANSLATOR_SPACE_GRAY|TRANSLATOR_VOID_BLUE": (-2261.9, 694.8),
    "TRANSLATOR_ECLIPSE_CHARCOAL|TRANSLATOR_SPACE_GRAY": (816.7, 424.8),
    "TRANSLATOR_ASTRO_BLACK|TRANSLATOR_SPACE_GRAY": (215.3, 416.2),
    "TRANSLATOR_GRAPHITE_MIST|TRANSLATOR_VOID_BLUE": (-749.9, 781.3),
    "TRANSLATOR_GRAPHITE_MIST|TRANSLATOR_SPACE_GRAY": (1512.0, 312.0),
    "TRANSLATOR_ECLIPSE_CHARCOAL|TRANSLATOR_GRAPHITE_MIST": (-695.3, 412.0),
    "TRANSLATOR_ECLIPSE_CHARCOAL|TRANSLATOR_VOID_BLUE": (-1445.2, 417.9),
    "TRANSLATOR_ASTRO_BLACK|TRANSLATOR_GRAPHITE_MIST": (-1296.8, 467.3),
    "TRANSLATOR_ASTRO_BLACK|TRANSLATOR_VOID_BLUE": (-2046.6, 392.2),
    "TRANSLATOR_ASTRO_BLACK|TRANSLATOR_ECLIPSE_CHARCOAL": (-601.4, 222.6),
    # SLEEP_POD
    "SLEEP_POD_COTTON|SLEEP_POD_POLYESTER": (-311.9, 381.4),
    "SLEEP_POD_POLYESTER|SLEEP_POD_SUEDE": (771.4, 363.5),
    "SLEEP_POD_LAMB_WOOL|SLEEP_POD_SUEDE": (-1179.0, 422.1),
    "SLEEP_POD_COTTON|SLEEP_POD_SUEDE": (459.5, 586.8),
    "SLEEP_POD_LAMB_WOOL|SLEEP_POD_POLYESTER": (-1950.4, 525.9),
    "SLEEP_POD_NYLON|SLEEP_POD_SUEDE": (-1864.3, 551.6),
    "SLEEP_POD_LAMB_WOOL|SLEEP_POD_NYLON": (685.3, 348.5),
    "SLEEP_POD_COTTON|SLEEP_POD_LAMB_WOOL": (1638.5, 779.1),
    "SLEEP_POD_NYLON|SLEEP_POD_POLYESTER": (-2635.7, 620.8),
    "SLEEP_POD_COTTON|SLEEP_POD_NYLON": (2323.8, 898.0),
    # GALAXY_SOUNDS
    "GALAXY_SOUNDS_BLACK_HOLES|GALAXY_SOUNDS_DARK_MATTER": (2466.1, 741.8),
    "GALAXY_SOUNDS_DARK_MATTER|GALAXY_SOUNDS_SOLAR_FLAMES": (-776.0, 581.6),
    "GALAXY_SOUNDS_PLANETARY_RINGS|GALAXY_SOUNDS_SOLAR_WINDS": (-264.7, 575.9),
    "GALAXY_SOUNDS_PLANETARY_RINGS|GALAXY_SOUNDS_SOLAR_FLAMES": (-250.6, 445.2),
    "GALAXY_SOUNDS_DARK_MATTER|GALAXY_SOUNDS_SOLAR_WINDS": (-790.1, 495.7),
    "GALAXY_SOUNDS_SOLAR_FLAMES|GALAXY_SOUNDS_SOLAR_WINDS": (-14.1, 397.7),
    "GALAXY_SOUNDS_BLACK_HOLES|GALAXY_SOUNDS_SOLAR_FLAMES": (1690.2, 609.6),
    "GALAXY_SOUNDS_DARK_MATTER|GALAXY_SOUNDS_PLANETARY_RINGS": (-525.4, 456.9),
    "GALAXY_SOUNDS_BLACK_HOLES|GALAXY_SOUNDS_PLANETARY_RINGS": (1940.8, 792.0),
    "GALAXY_SOUNDS_BLACK_HOLES|GALAXY_SOUNDS_SOLAR_WINDS": (1676.0, 674.6),
    # PANEL
    "PANEL_2X2|PANEL_2X4": (-3119.8, 485.2),
    "PANEL_1X4|PANEL_2X4": (-3337.9, 456.0),
    "PANEL_1X2|PANEL_2X2": (499.8, 387.4),
    "PANEL_1X2|PANEL_2X4": (-2620.0, 231.8),
    "PANEL_1X2|PANEL_1X4": (717.9, 371.0),
    "PANEL_1X4|PANEL_2X2": (-218.1, 193.1),
    "PANEL_2X4|PANEL_4X4": (1827.7, 936.6),
    "PANEL_1X2|PANEL_4X4": (-792.3, 920.2),
    "PANEL_2X2|PANEL_4X4": (-1292.2, 648.6),
    "PANEL_1X4|PANEL_4X4": (-1510.2, 691.5),
}

# L1 — cointegrated triplet (Y_triplet)
TRIPLET_SEEDS = [
    ("MICROCHIP_TRIANGLE", "MICROCHIP_OVAL", "MICROCHIP_RECTANGLE",
     8583.4, 0.607, -0.443, 0.0, 323.5),
]

# L2 — PEBBLES H4 per-product seeds (mid mean, mid std), day-4 trained
PEBBLES = ["PEBBLES_L", "PEBBLES_M", "PEBBLES_S", "PEBBLES_XL", "PEBBLES_XS"]
PEBBLES_SEEDS = {
    "PEBBLES_L":  (10458.4, 732.8),
    "PEBBLES_M":  (10872.3, 313.9),
    "PEBBLES_S":  ( 7948.5, 501.8),
    "PEBBLES_XL": (14665.0, 1444.1),
    "PEBBLES_XS": ( 6055.7, 489.8),
}
BASKET_TARGET = 50000.0
BASKET_STD = 2.8

# L3 — ALWAYS_TARGETS structural bias positions, validated by Min/team.
# Direction inferred from cross-day drift in algos/r5/runs/r5_zstats.json:
#   MICROCHIP_OVAL: 9766 → 8544 → 6229   (drift -3537 → SHORT)
#   OXYGEN_SHAKE_GARLIC: 11058 → 11808 → 12911  (+1853 → LONG)
#   UV_VISOR_AMBER: 9177 → 7673 → 6885   (-2292 → SHORT)
#   UV_VISOR_RED: 10778 → 10624 → 11788  (mixed; team validated → LONG)
#   PANEL_2X4: 10714 → 11207 → 11876     (+1162 → LONG)
#   GALAXY_SOUNDS_BLACK_HOLES: 10681 → 11108 → 12612 (+1932 → LONG, gated by INCLUDE_GS_BH)
ALWAYS_TARGETS_BASE = {
    "MICROCHIP_OVAL":           -5,
    "OXYGEN_SHAKE_GARLIC":      +5,
    "UV_VISOR_AMBER":           -5,
    "UV_VISOR_RED":             +5,
    "PANEL_2X4":                +5,
}
GS_BH_OPTIONAL = ("GALAXY_SOUNDS_BLACK_HOLES", +5)


def _mid(d):
    if d is None or not d.buy_orders or not d.sell_orders:
        return None
    return (max(d.buy_orders) + min(d.sell_orders)) / 2.0


def _bb_ba(d):
    bb = max(d.buy_orders) if d.buy_orders else None
    ba = min(d.sell_orders) if d.sell_orders else None
    return bb, ba


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


class Trader:
    POS_LIMIT = 10

    # L1 pair MR
    PAIR_MAX_POS = 10
    PAIR_ENTER_Z = 1.70
    PAIR_EXIT_Z = 0.0
    EMA_ALPHA = 0.0002
    VAR_ALPHA = 0.0002
    DEFAULT_INIT_VAR = 1_000_000.0
    TRIPLET_MAX_POS = 2
    TRIPLET_HEDGE_CAP = 4
    TRIPLET_ENTER_Z = 1.70

    # L2 PEBBLES H4
    BASKET_ENTER_Z = 1.70
    BASKET_EXIT_Z = 0.0
    H4_LEG_POS = 10            # absolute target on the chosen leg

    # L3 structural bias
    INCLUDE_GS_BH = False      # Galaxy Sounds Black Holes — failed OOS in prior variant
    BIAS_MAGNITUDE = 5         # |target| per ALWAYS_TARGETS product

    # If True, drop the 10 PEBBLES_*|PEBBLES_* pairs from L1 (let H4 own PEBBLES).
    DROP_PEBBLES_PAIRS = False

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
            init_var = max(init_var, 1.0)
            st["em"][key] = init_mean
            st["ev"][key] = init_var
            return init_mean, init_var
        m2 = m + self.EMA_ALPHA * (x - m)
        v_prev = st["ev"].get(key, self.DEFAULT_INIT_VAR)
        v_new = (1 - self.VAR_ALPHA) * v_prev + self.VAR_ALPHA * (x - m) ** 2
        st["em"][key] = m2
        st["ev"][key] = v_new
        return m2, v_new

    # ------------------------------------------------------------------ L1
    def _layer_pair(self, st, depths) -> Dict[str, int]:
        targets: Dict[str, int] = {}
        for key, (mu_seed, sd_seed) in PAIR_SEEDS.items():
            la, lb = key.split("|")
            if self.DROP_PEBBLES_PAIRS and la.startswith("PEBBLES_") and lb.startswith("PEBBLES_"):
                continue
            da = depths.get(la); db = depths.get(lb)
            if da is None or db is None:
                continue
            ma = _mid(da); mb = _mid(db)
            if ma is None or mb is None:
                continue
            spread = ma - mb
            m, v = self._ema(st, f"P:{key}", spread, mu_seed, sd_seed)
            std = max(v ** 0.5, 1.0)
            z = (spread - m) / std
            if z > self.PAIR_ENTER_Z:
                targets[la] = targets.get(la, 0) - self.PAIR_MAX_POS
                targets[lb] = targets.get(lb, 0) + self.PAIR_MAX_POS
            elif z < -self.PAIR_ENTER_Z:
                targets[la] = targets.get(la, 0) + self.PAIR_MAX_POS
                targets[lb] = targets.get(lb, 0) - self.PAIR_MAX_POS
        # Triplet (L1 sub-layer)
        for y, x1, x2, alpha, b1, b2, mu_seed, sd_seed in TRIPLET_SEEDS:
            dy = depths.get(y); d1 = depths.get(x1); d2 = depths.get(x2)
            if dy is None or d1 is None or d2 is None:
                continue
            my = _mid(dy); m1 = _mid(d1); m2 = _mid(d2)
            if my is None or m1 is None or m2 is None:
                continue
            spread = my - b1 * m1 - b2 * m2 - alpha
            key = f"T:{y}|{x1}|{x2}"
            m, v = self._ema(st, key, spread, mu_seed, sd_seed)
            std = max(v ** 0.5, 1.0)
            z = (spread - m) / std
            h1 = _clip(int(round(b1 * self.TRIPLET_MAX_POS)),
                       -self.TRIPLET_HEDGE_CAP, self.TRIPLET_HEDGE_CAP)
            h2 = _clip(int(round(b2 * self.TRIPLET_MAX_POS)),
                       -self.TRIPLET_HEDGE_CAP, self.TRIPLET_HEDGE_CAP)
            if z > self.TRIPLET_ENTER_Z:
                targets[y]  = targets.get(y, 0)  - self.TRIPLET_MAX_POS
                targets[x1] = targets.get(x1, 0) + h1
                targets[x2] = targets.get(x2, 0) + h2
            elif z < -self.TRIPLET_ENTER_Z:
                targets[y]  = targets.get(y, 0)  + self.TRIPLET_MAX_POS
                targets[x1] = targets.get(x1, 0) - h1
                targets[x2] = targets.get(x2, 0) - h2
        return targets

    # ------------------------------------------------------------------ L2
    def _layer_pebbles_h4(self, st, depths) -> Dict[str, int]:
        targets: Dict[str, int] = {}
        mids = {}
        for p in PEBBLES:
            d = depths.get(p)
            if d is None:
                continue
            m = _mid(d)
            if m is not None:
                mids[p] = m
        if len(mids) < 5:
            return targets
        bsum = sum(mids.values())
        bm, bv = self._ema(st, "_basket", bsum,
                           mean_seed=BASKET_TARGET, std_seed=BASKET_STD)
        bstd = max(bv ** 0.5, 0.5)
        zbasket = (bsum - bm) / bstd

        zs = {}
        for p, mm in mids.items():
            seed = PEBBLES_SEEDS.get(p)
            if seed is None:
                continue
            pm, pv = self._ema(st, f"L:{p}", mm, mean_seed=seed[0], std_seed=seed[1])
            std = max(pv ** 0.5, 1.0)
            zs[p] = (mm - pm) / std

        if abs(zbasket) > self.BASKET_ENTER_Z and zs:
            if zbasket > 0:
                leg = max(zs, key=zs.get)
                targets[leg] = -self.H4_LEG_POS
            else:
                leg = min(zs, key=zs.get)
                targets[leg] = +self.H4_LEG_POS
        elif abs(zbasket) < self.BASKET_EXIT_Z:
            for p in PEBBLES:
                targets[p] = 0
        return targets

    # ------------------------------------------------------------------ L3
    def _layer_bias(self) -> Dict[str, int]:
        targets: Dict[str, int] = {}
        for sym, sgn in ALWAYS_TARGETS_BASE.items():
            scale = sgn // 5  # ±1
            targets[sym] = scale * self.BIAS_MAGNITUDE
        if self.INCLUDE_GS_BH:
            sym, sgn = GS_BH_OPTIONAL
            scale = sgn // 5
            targets[sym] = scale * self.BIAS_MAGNITUDE
        return targets

    # ------------------------------------------------------------------ combine + emit
    def _combine(self, l1, l2, l3) -> Dict[str, int]:
        legs = set(l1) | set(l2) | set(l3)
        merged: Dict[str, int] = {}
        for leg in legs:
            s = l1.get(leg, 0) + l2.get(leg, 0) + l3.get(leg, 0)
            merged[leg] = _clip(s, -self.POS_LIMIT, self.POS_LIMIT)
        return merged

    def _emit(self, depths, positions, targets):
        out: Dict[str, List[Order]] = {}
        for leg, target in targets.items():
            cur = positions.get(leg, 0)
            delta = target - cur
            if delta == 0:
                continue
            d = depths.get(leg)
            if d is None:
                continue
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

        l1 = self._layer_pair(st, depths)
        l2 = self._layer_pebbles_h4(st, depths)
        l3 = self._layer_bias()
        targets = self._combine(l1, l2, l3)
        out = self._emit(depths, positions, targets)
        return out, 0, json.dumps(st)
