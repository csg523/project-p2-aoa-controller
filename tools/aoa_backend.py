#!/usr/bin/env python3
"""
AoA Backend Bridge — wraps simulate_pipeline.py logic for GUI consumption.

This module does NOT duplicate any core computation.  It imports and calls:
  - validator_run_values
  - perform_weighted_fusion
  - apply_kalman / EstimatorState
  - load_thresholds / thresholds_lookup
  - fsm_run

Two public classes:
  AoAProcessor  — stateful, call process_input() per data point
  CSVStreamer    — QThread that reads sim_input.csv row-by-row and emits signals
"""

from __future__ import annotations

import csv
import os
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple, List

from PyQt5.QtCore import QThread, pyqtSignal

# ── Import core pipeline functions (no changes to that file) ──────────
from simulate_pipeline import (
    ValidatorResult,
    EstimatorState,
    FSMResult,
    validator_run_values,
    perform_weighted_fusion,
    apply_kalman,
    load_thresholds,
    thresholds_lookup,
    fsm_run,
    DEFAULT_AIRCRAFT_TYPE,
)


# ── Result container returned by AoAProcessor.process_input() ─────────
@dataclass
class ProcessResult:
    aoa: float = 0.0
    fused_aoa: float = 0.0
    submode: str = "NORMAL"
    limit_low: float = 0.0
    limit_high: float = 20.0
    num_valid: int = 0
    median: Optional[float] = None
    mode: str = "CRUISE"
    airspeed: Optional[float] = None
    s1: Optional[float] = None
    s2: Optional[float] = None
    s3: Optional[float] = None


# ── CSV row container ─────────────────────────────────────────────────
@dataclass
class CSVRow:
    idx: int = 0
    ts: int = 0
    mode: str = ""
    s1: Optional[float] = None
    s2: Optional[float] = None
    s3: Optional[float] = None
    airspeed: Optional[float] = None


# ══════════════════════════════════════════════════════════════════════
#  AoAProcessor — stateful pipeline runner
# ══════════════════════════════════════════════════════════════════════

class AoAProcessor:
    """Wrap the full pipeline (validate → fuse → Kalman → threshold → FSM)
    into a single ``process_input`` call.  Maintains estimator state across
    successive calls so the Kalman filter converges properly.
    """

    def __init__(
        self,
        thresholds_csv: str | None = None,
        aircraft_type: str = DEFAULT_AIRCRAFT_TYPE,
    ):
        if thresholds_csv is None:
            # Default path relative to this file
            base = os.path.dirname(os.path.abspath(__file__))
            thresholds_csv = os.path.join(
                base,
                "..",
                "components",
                "aoa_controller",
                "data",
                "thresholds.csv",
            )
        self.thresholds: Dict[Tuple[str, str], Tuple[float, float]] = load_thresholds(
            thresholds_csv
        )
        self.aircraft_type = aircraft_type
        self.estimator = EstimatorState()
        self._fsm_state = "NORMAL"

    # ── public ────────────────────────────────────────────────────────
    def process_input(
        self,
        s1: Optional[float],
        s2: Optional[float],
        s3: Optional[float],
        mode: str = "CRUISE",
        airspeed: Optional[float] = None,
    ) -> ProcessResult:
        vr: ValidatorResult = validator_run_values(s1, s2, s3)
        fused: float = perform_weighted_fusion(vr)
        apply_kalman(fused, self.estimator)
        final_aoa: float = self.estimator.final_aoa

        low, high = thresholds_lookup(self.thresholds, self.aircraft_type, mode)
        fsm: FSMResult = fsm_run(final_aoa, low, high, self._fsm_state)
        self._fsm_state = fsm.state

        return ProcessResult(
            aoa=final_aoa,
            fused_aoa=fused,
            submode=fsm.state,
            limit_low=low,
            limit_high=high,
            num_valid=vr.num_valid,
            median=vr.median,
            mode=mode,
            airspeed=airspeed,
            s1=s1,
            s2=s2,
            s3=s3,
        )

    def reset(self):
        """Reset estimator & FSM state (e.g. when switching modes)."""
        self.estimator = EstimatorState()
        self._fsm_state = "NORMAL"

    @property
    def current_submode(self) -> str:
        return self._fsm_state


# ══════════════════════════════════════════════════════════════════════
#  CSVStreamer — QThread for dynamic (continuous) CSV playback
# ══════════════════════════════════════════════════════════════════════

class CSVStreamer(QThread):
    """Read *sim_input.csv* row-by-row and emit a signal for each row.

    Signals
    -------
    row_ready(CSVRow)
        Emitted for every valid CSV row, with a configurable delay between
        rows so the UI can animate in near-real-time.
    finished_stream()
        Emitted once when the entire CSV has been played.
    """

    row_ready = pyqtSignal(object)       # CSVRow
    finished_stream = pyqtSignal()

    def __init__(
        self,
        csv_path: str | None = None,
        interval_ms: int = 150,
        parent=None,
    ):
        super().__init__(parent)
        if csv_path is None:
            base = os.path.dirname(os.path.abspath(__file__))
            csv_path = os.path.join(
                base,
                "..",
                "components",
                "aoa_controller",
                "data",
                "sim_input.csv",
            )
        self.csv_path = csv_path
        self.interval_ms = interval_ms
        self._stop_flag = False
        self._pause_flag = False

    # ── control ───────────────────────────────────────────────────────
    def request_stop(self):
        self._stop_flag = True

    def set_paused(self, paused: bool):
        self._pause_flag = paused

    def set_speed(self, interval_ms: int):
        self.interval_ms = max(10, interval_ms)

    # ── thread body ───────────────────────────────────────────────────
    def run(self):
        self._stop_flag = False
        self._pause_flag = False

        def _float_or_none(val: str) -> Optional[float]:
            val = val.strip()
            if not val:
                return None
            try:
                return float(val)
            except ValueError:
                return None

        try:
            with open(self.csv_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if self._stop_flag:
                        break
                    while self._pause_flag and not self._stop_flag:
                        time.sleep(0.05)
                    if self._stop_flag:
                        break

                    s1 = _float_or_none(row.get("s1", ""))
                    s2 = _float_or_none(row.get("s2", ""))
                    s3 = _float_or_none(row.get("s3", ""))
                    ts_raw = row.get("ts", "")
                    if not ts_raw.strip():
                        continue
                    try:
                        ts = int(float(ts_raw))
                    except ValueError:
                        continue

                    idx_raw = row.get("idx", "0")
                    try:
                        idx = int(idx_raw)
                    except ValueError:
                        idx = 0

                    mode = (row.get("mode") or "").strip()
                    airspeed = _float_or_none(row.get("airspeed", ""))

                    csv_row = CSVRow(
                        idx=idx,
                        ts=ts,
                        mode=mode if mode else "CRUISE",
                        s1=s1,
                        s2=s2,
                        s3=s3,
                        airspeed=airspeed,
                    )
                    self.row_ready.emit(csv_row)
                    time.sleep(self.interval_ms / 1000.0)
        except FileNotFoundError:
            pass

        self.finished_stream.emit()
