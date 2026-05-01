#!/usr/bin/env python3
import csv
import time
import argparse
from dataclasses import dataclass
from typing import Optional, Tuple, Dict

OUTLIER_THRESHOLD_DEG = 5.0
KALMAN_PROCESS_NOISE = 0.01
KALMAN_MEASUREMENT_NOISE = 0.5
FSM_CAUTION_MARGIN_DEG = 2.0
FSM_PROTECTION_MARGIN_DEG = 0.5
DEFAULT_AIRCRAFT_TYPE = "Aircraft_A"

@dataclass
class ValidatorResult:
    s1: Optional[float]
    s2: Optional[float]
    s3: Optional[float]
    median: Optional[float]
    valid1: bool
    valid2: bool
    valid3: bool
    num_valid: int

@dataclass
class EstimatorState:
    fused_aoa: float = 0.0
    final_aoa: float = 0.0
    est_variance: float = 1.0

@dataclass
class FSMResult:
    state: str
    aoa: float
    limit_low: float
    limit_high: float


def calculate_median(a, b, c):
    vals = [a, b, c]
    vals_sorted = sorted([(v if v is not None else float('inf')) for v in vals])
    med = vals_sorted[1]
    if med == float('inf'):
        return None
    return med


def validator_run_values(s1, s2, s3) -> ValidatorResult:
    vals = [s1, s2, s3]
    median = calculate_median(s1, s2, s3)
    valid = [False, False, False]
    num_valid = 0
    if median is None:
        return ValidatorResult(s1, s2, s3, None, False, False, False, 0)
    diffs = []
    for i, v in enumerate(vals):
        if v is None:
            diffs.append(float('inf'))
            valid[i] = False
        else:
            d = abs(v - median)
            diffs.append(d)
            valid[i] = (d <= OUTLIER_THRESHOLD_DEG)
            if valid[i]:
                num_valid += 1
    return ValidatorResult(s1, s2, s3, median, valid[0], valid[1], valid[2], num_valid)


def perform_weighted_fusion(vr: ValidatorResult) -> float:
    if vr.num_valid == 0:
        return 0.0
    s = 0.0
    count = 0
    if vr.valid1 and vr.s1 is not None:
        s += vr.s1; count += 1
    if vr.valid2 and vr.s2 is not None:
        s += vr.s2; count += 1
    if vr.valid3 and vr.s3 is not None:
        s += vr.s3; count += 1
    return (s / count) if count > 0 else 0.0


def apply_kalman(measurement: float, state: EstimatorState):
    prior = state.final_aoa
    prior_var = state.est_variance + KALMAN_PROCESS_NOISE
    gain = prior_var / (prior_var + KALMAN_MEASUREMENT_NOISE)
    state.final_aoa = prior + gain * (measurement - prior)
    state.est_variance = (1.0 - gain) * prior_var


def load_thresholds(csvfile: str) -> Dict[Tuple[str,str], Tuple[float,float]]:
    table = {}
    try:
        with open(csvfile, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row: continue
                if row[0].strip().startswith('#'): continue
                parts = [p.strip() for p in row]
                if len(parts) < 4: continue
                key = (parts[0], parts[1])
                try:
                    low = float(parts[2]); high = float(parts[3])
                    table[key] = (low, high)
                except ValueError:
                    continue
    except FileNotFoundError:
        pass
    return table


def thresholds_lookup(table: Dict[Tuple[str,str], Tuple[float,float]], aircraft_type: str, flight_mode: str) -> Tuple[float,float]:
    k = (aircraft_type, flight_mode)
    if k in table:
        return table[k]
    for (a,m), (low,high) in table.items():
        if m == flight_mode:
            return (low,high)
    return (0.0, 20.0)


def fsm_run(calculated_aoa: float, low: float, high: float, current_state: Optional[str]) -> FSMResult:
    limit_high = high
    limit_prot = limit_high - FSM_PROTECTION_MARGIN_DEG
    limit_caution = limit_high - FSM_CAUTION_MARGIN_DEG
    new_state = 'NORMAL'
    if calculated_aoa > limit_high:
        new_state = 'OVERRIDE'
    elif calculated_aoa > limit_prot:
        new_state = 'PROTECTION'
    elif calculated_aoa > limit_caution:
        new_state = 'CAUTION'
    return FSMResult(new_state, calculated_aoa, low, high)


def parse_line(line: str):
    parts = [p.strip() for p in line.split(',')]
    if len(parts) < 7:
        return None
    try:
        idx = int(parts[0])
    except:
        idx = None
    try:
        ts = int(parts[1])
    except:
        ts = None
    mode = parts[2] if parts[2] != '' else None
    def tof(x):
        try:
            return float(x) if x != '' else None
        except:
            return None
    s1 = tof(parts[3]); s2 = tof(parts[4]); s3 = tof(parts[5]); airspeed = tof(parts[6])
    return {'idx': idx, 'ts': ts, 'mode': mode, 's1': s1, 's2': s2, 's3': s3, 'airspeed': airspeed}


def run_sim(csvfile: str, thresholds_csv: str, interval_ms: int, aircraft_type: str = DEFAULT_AIRCRAFT_TYPE):
    thresholds = load_thresholds(thresholds_csv)
    estimator = EstimatorState()
    current_fsm_state = 'NORMAL'

    with open(csvfile, 'r') as f:
        for raw in f:
            raw = raw.strip()
            if not raw or raw.startswith('#'): continue
            parsed = parse_line(raw)
            if parsed is None:
                continue
            vr = validator_run_values(parsed['s1'], parsed['s2'], parsed['s3'])
            fused = perform_weighted_fusion(vr)
            apply_kalman(fused, estimator)
            final = estimator.final_aoa
            mode = parsed['mode'] or 'CRUISE'
            low, high = thresholds_lookup(thresholds, aircraft_type, mode)
            fsm = fsm_run(final, low, high, current_fsm_state)
            current_fsm_state = fsm.state
            def fmt(x, fmt_spec='6.2f'):
                if x is None:
                    return 'NA'.rjust(len(fmt_spec))
                try:
                    return format(x, fmt_spec)
                except Exception:
                    return str(x)

            print(
                f"IDX={parsed['idx']!s:3} TS={parsed['ts']!s:5} MODE={mode:8} "
                f"S1={fmt(parsed['s1'],'6.2f')} S2={fmt(parsed['s2'],'6.2f')} S3={fmt(parsed['s3'],'6.2f')} | "
                f"MED={fmt(vr.median,'5.2f')} VAL=[{int(vr.valid1)},{int(vr.valid2)},{int(vr.valid3)}] NUM={vr.num_valid} "
                f"FUSED={fmt(fused,'5.2f')} AOA={fmt(final,'6.2f')} FSM={fsm.state} LIMIT_H={fmt(high,'4.1f')}"
            )
            time.sleep(interval_ms/1000.0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Simulate firmware pipeline')
    parser.add_argument('--file', default='components/aoa_controller/data/sim_input.csv')
    parser.add_argument('--thresholds', default='components/aoa_controller/data/thresholds.csv')
    parser.add_argument('--interval', type=int, default=50)
    parser.add_argument('--aircraft', default=DEFAULT_AIRCRAFT_TYPE)
    args = parser.parse_args()
    run_sim(args.file, args.thresholds, args.interval, args.aircraft)
