# analyzer/core_advanced.py
"""
Advanced analyzer for OBIXConfig Doctor
- Supports thrust-current curves (CSV)
- Computes TWR, flight time (from current or from thrust->current lookup)
- Models battery usable capacity, voltage sag (internal resistance)
- Monte Carlo sampling for uncertainty estimates
"""

from typing import List, Dict, Tuple, Optional
import csv
import math
import random
import statistics

# ---------------------------
# Utilities: interpolation
# ---------------------------
def linear_interpolate(x0, y0, x1, y1, x):
    if x1 == x0:
        return (y0 + y1) / 2.0
    return y0 + (y1 - y0) * ( (x - x0) / (x1 - x0) )

def interp_lookup(table: List[Tuple[float, float]], x: float) -> float:
    """
    table: sorted list of (x_value, y_value)
    returns interpolated y at given x
    If x outside range, returns nearest endpoint value.
    """
    if not table:
        raise ValueError("Empty table")
    # If x is outside bounds
    if x <= table[0][0]:
        return table[0][1]
    if x >= table[-1][0]:
        return table[-1][1]
    # find enclosing interval
    for i in range(len(table) - 1):
        x0, y0 = table[i]
        x1, y1 = table[i+1]
        if x0 <= x <= x1:
            return linear_interpolate(x0, y0, x1, y1, x)
    # fallback
    return table[-1][1]

# ---------------------------
# CSV loader for thrust curve
# ---------------------------
def load_thrust_curve_csv(path: str) -> List[Tuple[float, float, float]]:
    """
    Load CSV with columns: throttle_pct, thrust_g, current_a (optionally voltage)
    Returns list of tuples (throttle_pct, thrust_g, current_a)
    throttle_pct expected 0-100
    """
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            # flexible field names
            t = float(r.get('throttle', r.get('throttle_pct', r.get('throttle%','0'))))
            thrust = float(r.get('thrust_g', r.get('thrust','0')))
            current = float(r.get('current_a', r.get('current','0')))
            rows.append((t, thrust, current))
    # sort by throttle
    rows.sort(key=lambda x: x[0])
    return rows

def build_thrust_to_current_tables(curve_rows: List[Tuple[float,float,float]]):
    """
    Build two lookup tables:
    - thrust_to_current: sorted by thrust_g -> current_a
    - throttle_to_thrust: sorted by throttle_pct -> thrust_g
    Returns (thrust_table, throttle_table)
    thrust_table: list of (thrust_g, current_a)
    throttle_table: list of (throttle_pct, thrust_g)
    """
    throttle_table = [(r[0], r[1]) for r in curve_rows]
    thrust_table = sorted([(r[1], r[2]) for r in curve_rows], key=lambda x: x[0])
    return thrust_table, throttle_table

# ---------------------------
# Core physical calculations
# ---------------------------
def total_thrust_from_motor(thrust_per_motor_g: float, motor_count: int) -> float:
    return thrust_per_motor_g * motor_count

def thrust_to_weight_ratio(total_thrust_g: float, weight_g: float) -> float:
    if weight_g <= 0:
        raise ValueError("weight_g must be > 0")
    return float(total_thrust_g) / float(weight_g)

def estimate_flight_time_from_current(mAh: float, avg_current_a: float,
                                      usable_fraction: float = 0.8) -> float:
    """
    Returns minutes.
    """
    if mAh <= 0 or avg_current_a <= 0:
        raise ValueError("mAh and avg_current_a must be > 0")
    Ah = mAh / 1000.0
    usable_Ah = Ah * usable_fraction
    hours = usable_Ah / float(avg_current_a)
    minutes = hours * 60.0
    return minutes

def estimate_flight_time_from_power(mAh: float, nominal_voltage_v: float, avg_power_w: float,
                                   usable_fraction: float = 0.8) -> float:
    """
    avg_power_w: average system power in Watts
    Returns minutes.
    """
    if mAh <= 0 or nominal_voltage_v <= 0 or avg_power_w <= 0:
        raise ValueError("mAh, voltage, power must be > 0")
    Ah = mAh / 1000.0
    Wh = Ah * nominal_voltage_v
    usable_Wh = Wh * usable_fraction
    hours = usable_Wh / float(avg_power_w)
    minutes = hours * 60.0
    return minutes

# battery voltage sag: V_loaded = V_nominal - IR * current
def voltage_under_load(nominal_v: float, total_current_a: float, internal_resistance_ohm: float) -> float:
    return nominal_v - (internal_resistance_ohm * total_current_a)

# estimate avg current from thrust using thrust->current table (interpolation)
def estimate_current_from_thrust_per_motor(thrust_per_motor_g: float, thrust_table: List[Tuple[float,float]]) -> float:
    """
    thrust_table: list of (thrust_g, current_a)
    Returns current per motor (A)
    """
    return interp_lookup(thrust_table, thrust_per_motor_g)

# convert current into power (W) using voltage (account for sag)
def current_to_power(total_current_a: float, nominal_v: float, internal_resistance_ohm: float) -> Tuple[float, float]:
    """
    Returns tuple (v_loaded, power_w)
    """
    v_loaded = voltage_under_load(nominal_v, total_current_a, internal_resistance_ohm)
    if v_loaded <= 0:
        v_loaded = nominal_v * 0.5  # fail-safe fallback
    power = v_loaded * total_current_a
    return v_loaded, power

# ---------------------------
# High-level compute function
# ---------------------------
def compute_advanced(params: Dict, thrust_curve_rows: Optional[List[Tuple[float,float,float]]] = None) -> Dict:
    """
    params: expected keys (examples and defaults provided)
      - motor_count (int)
      - thrust_per_motor_g (float) OR throttle_pct (float) to lookup thrust
      - weight_g (float)
      - mAh (float)
      - nominal_voltage_v (float)
      - usable_fraction (float) default 0.8
      - internal_resistance_ohm (float) default 0.05
      - system_current_others_a (float) e.g. vtx, fc, leds default 2.0
      - thrust_curve_rows: optional loaded CSV rows (throttle, thrust, current) for better mapping
    returns dict with keys:
      - total_thrust_g, twr, est_flight_time_min_by_current, est_flight_time_min_by_power, notes, distributions (optional)
    """
    # defaults
    motor_count = int(params.get("motor_count", 4))
    weight_g = float(params.get("weight_g", 1200.0))
    mAh = float(params.get("mAh", 1500.0))
    nominal_voltage_v = float(params.get("nominal_voltage_v", 14.8))
    usable_fraction = float(params.get("usable_fraction", 0.8))
    internal_resistance_ohm = float(params.get("internal_resistance_ohm", 0.05))
    system_current_others_a = float(params.get("system_current_others_a", 2.0))
    motor_efficiency_factor = float(params.get("motor_efficiency_factor", 0.95))  # placeholder

    # Prepare thrust/current lookup if provided
    thrust_table = None
    if thrust_curve_rows:
        try:
            thrust_table, throttle_table = build_thrust_to_current_tables(thrust_curve_rows)
        except Exception:
            thrust_table = None

    # Determine thrust per motor
    if "thrust_per_motor_g" in params:
        thrust_per_motor_g = float(params["thrust_per_motor_g"])
    elif "throttle_pct" in params and thrust_curve_rows:
        throttle_pct = float(params["throttle_pct"])
        # find thrust from throttle_table
        # throttle_table stored as (throttle_pct, thrust_g)
        throttle_table = [(r[0], r[1]) for r in thrust_curve_rows]
        thrust_per_motor_g = interp_lookup(throttle_table, throttle_pct)
    else:
        raise ValueError("Provide thrust_per_motor_g or throttle_pct with thrust_curve_rows")

    total_thrust_g = total_thrust_from_motor(thrust_per_motor_g, motor_count)
    twr = thrust_to_weight_ratio(total_thrust_g, weight_g)

    # Estimate current per motor from thrust_table if available, otherwise from user-supplied avg_current_per_motor
    if thrust_table:
        current_per_motor_a = estimate_current_from_thrust_per_motor(thrust_per_motor_g, thrust_table)
    else:
        # fallback: require user to provide avg_current_per_motor or avg_current_total
        if "avg_current_per_motor" in params:
            current_per_motor_a = float(params["avg_current_per_motor"])
        elif "avg_current_total" in params:
            total_current_a = float(params["avg_current_total"])
            current_per_motor_a = total_current_a / motor_count
        else:
            raise ValueError("Need thrust_table or avg_current_per_motor/avg_current_total to estimate current")

    total_current_a = current_per_motor_a * motor_count + system_current_others_a

    # adjust for motor efficiency factor (simple adjustment on power)
    v_loaded, avg_power_w = current_to_power(total_current_a, nominal_voltage_v, internal_resistance_ohm)
    avg_power_w /= motor_efficiency_factor  # increase power to account for losses

    # Flight time estimates
    flight_time_min_current_based = estimate_flight_time_from_current(mAh, total_current_a, usable_fraction)
    flight_time_min_power_based = estimate_flight_time_from_power(mAh, nominal_voltage_v, avg_power_w, usable_fraction)

    result = {
        "thrust_per_motor_g": thrust_per_motor_g,
        "motor_count": motor_count,
        "total_thrust_g": total_thrust_g,
        "weight_g": weight_g,
        "twr": twr,
        "current_per_motor_a": current_per_motor_a,
        "total_current_a": total_current_a,
        "v_loaded_v": v_loaded,
        "avg_power_w": avg_power_w,
        "flight_time_min_current_based": flight_time_min_current_based,
        "flight_time_min_power_based": flight_time_min_power_based,
        "notes": []
    }

    # add helpful notes
    if thrust_table:
        result["notes"].append("Used thrust->current mapping from provided thrust curve.")
    else:
        result["notes"].append("Used avg_current provided; no thrust curve available.")
    if flight_time_min_current_based > flight_time_min_power_based * 1.2:
        result["notes"].append("Current-based estimate much larger than power-based estimate; check voltage/internal resistance or avg_current.")
    return result

# ---------------------------
# Monte Carlo uncertainty quantification
# ---------------------------
def monte_carlo_estimate(params: Dict, thrust_curve_rows: Optional[List[Tuple[float,float,float]]] = None,
                         n_samples: int = 1000, random_seed: Optional[int] = None) -> Dict:
    """
    Run Monte Carlo sampling over uncertain inputs:
    Uncertainties considered (if available in params):
      - thrust_per_motor_g: +- perc (default 0.05)
      - mAh: +- perc (default 0.05)
      - avg_current_per_motor: +- perc (default 0.10) OR inferred from thrust curve (with thrust error)
      - usable_fraction: small variation
    Returns distribution percentiles for TWR and flight_time (median, 10th, 90th)
    """
    if random_seed is not None:
        random.seed(random_seed)

    # extract nominal values and perc uncertainties
    thrust_nom = float(params.get("thrust_per_motor_g", 0.0))
    thrust_pct_unc = float(params.get("thrust_uncertainty_pct", 0.05))  # 5%
    mAh_nom = float(params.get("mAh", 1500.0))
    mAh_pct_unc = float(params.get("mAh_uncertainty_pct", 0.05))
    usable_nom = float(params.get("usable_fraction", 0.8))
    usable_unc = float(params.get("usable_uncertainty_pct", 0.03))
    motor_count = int(params.get("motor_count", 4))
    # current uncertainty if provided
    avg_current_per_motor_nom = float(params.get("avg_current_per_motor", params.get("avg_current_per_motor", 0.0)))
    avg_current_unc = float(params.get("avg_current_uncertainty_pct", 0.10))

    twr_samples = []
    time_samples = []

    # If thrust_curve provided, build thrust_table for mapping
    thrust_table = None
    if thrust_curve_rows:
        thrust_table, _ = build_thrust_to_current_tables(thrust_curve_rows)

    for i in range(n_samples):
        # sample thrust per motor
        thrust_sample = random.uniform(thrust_nom*(1-thrust_pct_unc), thrust_nom*(1+thrust_pct_unc))
        # sample mAh
        mAh_sample = random.uniform(mAh_nom*(1-mAh_pct_unc), mAh_nom*(1+mAh_pct_unc))
        # sample usable fraction
        usable_sample = random.uniform(usable_nom*(1-usable_unc), usable_nom*(1+usable_unc))
        # estimate current per motor for this sample
        if thrust_table:
            curr_per_motor_sample = estimate_current_from_thrust_per_motor(thrust_sample, thrust_table)
            # add noisy uncertainty
            curr_per_motor_sample *= random.uniform(1-avg_current_unc, 1+avg_current_unc)
        else:
            if avg_current_per_motor_nom <= 0:
                raise ValueError("avg_current_per_motor must be provided if no thrust table for MC")
            curr_per_motor_sample = random.uniform(avg_current_per_motor_nom*(1-avg_current_unc),
                                                   avg_current_per_motor_nom*(1+avg_current_unc))
        total_current_sample = curr_per_motor_sample * motor_count + float(params.get("system_current_others_a", 2.0))
        # compute flight time (current-based)
        time_min = estimate_flight_time_from_current(mAh_sample, total_current_sample, usable_sample)
        total_thrust_sample = thrust_sample * motor_count
        twr_sample = thrust_to_weight_ratio(total_thrust_sample, float(params.get("weight_g", 1200.0)))

        twr_samples.append(twr_sample)
        time_samples.append(time_min)

    def pctiles(data):
        data_sorted = sorted(data)
        def p(pct):
            k = (len(data_sorted)-1) * (pct/100.0)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return data_sorted[int(k)]
            d0 = data_sorted[int(f)] * (c - k)
            d1 = data_sorted[int(c)] * (k - f)
            return d0 + d1
        return {
            "p10": p(10),
            "p50": p(50),
            "p90": p(90),
            "mean": statistics.mean(data_sorted)
        }

    return {
        "twr": pctiles(twr_samples),
        "flight_time_min": pctiles(time_samples),
        "samples": len(twr_samples)
    }