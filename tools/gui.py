#!/usr/bin/env python3
"""AoA Controller GUI — PyQt5 application with real-time visualization."""

import sys, os, math, time, threading, re, numpy as np
import serial
import serial.tools.list_ports
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, pyqtSignal, QRectF
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
    QButtonGroup, QGroupBox, QFrame, QSlider, QSizePolicy, QComboBox,
    QTextEdit, QCheckBox,
)
from PyQt5.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient,
    QPainterPath, QPolygonF,
)
from PyQt5 import QtCore
import pyqtgraph as pg

# Add tools dir to path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aoa_backend import AoAProcessor, CSVStreamer, ProcessResult, CSVRow

# ── Color Palette ─────────────────────────────────────────────────────
BG_DARK      = "#0f1117"
BG_PANEL     = "#1a1d27"
BG_CARD      = "#232738"
BORDER       = "#2e3348"
TEXT_PRIMARY  = "#e8eaed"
TEXT_DIM      = "#8b8fa3"
ACCENT_BLUE  = "#4c9aff"
ACCENT_CYAN  = "#36d6c3"
GREEN        = "#34d399"
AMBER        = "#fbbf24"
ORANGE       = "#f97316"
RED          = "#ef4444"
PURPLE       = "#a78bfa"

SUBMODE_COLORS = {
    "NORMAL": GREEN, "CAUTION": AMBER,
    "PROTECTION": ORANGE, "OVERRIDE": RED,
}

GLOBAL_STYLE = f"""
QMainWindow, QWidget {{ background: {BG_DARK}; color: {TEXT_PRIMARY}; font-family: 'Inter','Segoe UI',sans-serif; }}
QGroupBox {{ background: {BG_PANEL}; border: 1px solid {BORDER}; border-radius: 10px; margin-top: 14px; padding: 14px 10px 10px 10px; font-size: 13px; font-weight: 600; color: {ACCENT_CYAN}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px; }}
QLineEdit {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 10px; color: {TEXT_PRIMARY}; font-size: 13px; }}
QLineEdit:focus {{ border-color: {ACCENT_BLUE}; }}
QPushButton {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px; padding: 8px 18px; color: {TEXT_PRIMARY}; font-size: 13px; font-weight: 600; }}
QPushButton:hover {{ background: {BORDER}; border-color: {ACCENT_BLUE}; }}
QPushButton:checked {{ background: {ACCENT_BLUE}; color: #fff; border-color: {ACCENT_BLUE}; }}
QPushButton:disabled {{ opacity: 0.4; color: {TEXT_DIM}; }}
QRadioButton {{ color: {TEXT_PRIMARY}; font-size: 13px; spacing: 6px; }}
QRadioButton::indicator {{ width: 14px; height: 14px; }}
QSlider::groove:horizontal {{ background: {BORDER}; height: 4px; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ACCENT_BLUE}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}
QLabel {{ color: {TEXT_PRIMARY}; }}
QComboBox {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 6px; padding: 6px 10px; color: {TEXT_PRIMARY}; font-size: 13px; }}
"""


# ══════════════════════════════════════════════════════════════════════
#  Flight Animation Widget
# ══════════════════════════════════════════════════════════════════════
class FlightAnimationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.aoa = 0.0
        self.mode = "CRUISE"
        self.submode = "NORMAL"
        self.airspeed = 0.0
        self._altitude_frac = 0.5
        self.setMinimumSize(340, 260)

    def update_state(self, aoa, mode, submode, airspeed):
        self.aoa = aoa
        self.mode = mode
        self.submode = submode
        self.airspeed = airspeed or 0
        # altitude fraction from mode
        alt_map = {"TAKEOFF": 0.3, "CLIMB": 0.55, "CRUISE": 0.75, "LANDING": 0.35}
        target = alt_map.get(mode, 0.5)
        self._altitude_frac += (target - self._altitude_frac) * 0.15
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Sky gradient
        sky = QLinearGradient(0, 0, 0, h)
        sky.setColorAt(0.0, QColor("#0c1445"))
        sky.setColorAt(0.6, QColor("#1a3a6e"))
        sky.setColorAt(1.0, QColor("#2d6a4f"))
        p.fillRect(0, 0, w, h, sky)

        # Ground
        ground_y = int(h * 0.82)
        gnd = QLinearGradient(0, ground_y, 0, h)
        gnd.setColorAt(0, QColor("#1b4332"))
        gnd.setColorAt(1, QColor("#0b1f15"))
        p.fillRect(0, ground_y, w, h - ground_y, gnd)

        # Horizon line
        p.setPen(QPen(QColor(ACCENT_CYAN), 1, Qt.DashLine))
        p.drawLine(0, ground_y, w, ground_y)

        # Aircraft position
        cx = w // 2
        cy = int(h * (1.0 - self._altitude_frac * 0.7) - 20)

        p.save()
        p.translate(cx, cy)
        angle = -self.aoa  # 1:1 mapping with actual AoA
        angle = max(-40, min(40, angle))
        p.rotate(angle)

        # Draw aircraft body
        color = QColor(SUBMODE_COLORS.get(self.submode, ACCENT_BLUE))
        p.setPen(QPen(color, 2))
        p.setBrush(QBrush(color.darker(150)))

        # Fuselage
        body = QPainterPath()
        body.moveTo(50, 0)
        body.lineTo(-30, -5)
        body.lineTo(-45, 0)
        body.lineTo(-30, 5)
        body.closeSubpath()
        p.drawPath(body)

        # Wings
        p.setPen(QPen(color, 2))
        wing = QPainterPath()
        wing.moveTo(5, -4)
        wing.lineTo(-15, -28)
        wing.lineTo(-22, -28)
        wing.lineTo(-10, -4)
        p.drawPath(wing)
        wing2 = QPainterPath()
        wing2.moveTo(5, 4)
        wing2.lineTo(-15, 28)
        wing2.lineTo(-22, 28)
        wing2.lineTo(-10, 4)
        p.drawPath(wing2)

        # Tail
        tail = QPainterPath()
        tail.moveTo(-38, -2)
        tail.lineTo(-48, -16)
        tail.lineTo(-52, -16)
        tail.lineTo(-44, -2)
        p.drawPath(tail)

        p.restore()

        # HUD overlay
        p.setPen(QColor(TEXT_PRIMARY))
        font = QFont("Inter", 11, QFont.Bold)
        p.setFont(font)
        p.drawText(12, 22, f"MODE: {self.mode}")
        p.drawText(12, 40, f"AoA: {self.aoa:.2f}°")
        p.drawText(12, 58, f"SPD: {self.airspeed:.0f} kts")

        # Submode badge
        sm_color = QColor(SUBMODE_COLORS.get(self.submode, GREEN))
        p.setPen(Qt.NoPen)
        p.setBrush(sm_color)
        badge_w = 100
        p.drawRoundedRect(w - badge_w - 12, 8, badge_w, 24, 6, 6)
        p.setPen(QColor("#000"))
        p.setFont(QFont("Inter", 10, QFont.Bold))
        p.drawText(w - badge_w - 12, 8, badge_w, 24, Qt.AlignCenter, self.submode)
        p.end()


# ══════════════════════════════════════════════════════════════════════
#  LED Indicator Widget
# ══════════════════════════════════════════════════════════════════════
class LEDWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self._on = True
        self._color = QColor(GREEN)
        self._blink = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._toggle)
        self._timer.start(500)

    def set_state(self, submode):
        if submode == "NORMAL":
            self._color = QColor(GREEN)
            self._blink = False
            self._on = True
        elif submode == "CAUTION":
            self._color = QColor(AMBER)
            self._blink = True
        elif submode == "PROTECTION":
            self._color = QColor(ORANGE)
            self._blink = True
        else:
            self._color = QColor(RED)
            self._blink = True
        self.update()

    def _toggle(self):
        if self._blink:
            self._on = not self._on
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self._on:
            glow = QColor(self._color)
            glow.setAlpha(60)
            p.setBrush(glow)
            p.setPen(Qt.NoPen)
            p.drawEllipse(2, 2, 24, 24)
            p.setBrush(self._color)
        else:
            p.setBrush(QColor(BG_CARD))
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawEllipse(5, 5, 18, 18)
        p.end()


# ══════════════════════════════════════════════════════════════════════
#  Serial Worker — background thread for ESP32 UART communication
# ══════════════════════════════════════════════════════════════════════
class SerialWorker(QtCore.QThread):
    """Background thread: reads ESP32 log lines and emits them as signals."""
    line_received = pyqtSignal(str)   # raw RX line
    status_parsed = pyqtSignal(str)   # parsed STATUS field (e.g. "CAUTION")
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ser = None
        self._stop = False
        self._lock = threading.Lock()

    def open_port(self, port: str, baud: int = 115200):
        self.close_port()
        try:
            self._ser = serial.Serial(port, baud, timeout=0.3)
            time.sleep(0.1)
            return True
        except Exception as e:
            self.error_occurred.emit(str(e))
            return False

    def close_port(self):
        with self._lock:
            if self._ser and self._ser.is_open:
                try:
                    self._ser.close()
                except Exception:
                    pass
            self._ser = None

    @property
    def is_connected(self):
        return self._ser is not None and self._ser.is_open

    def send(self, text: str):
        with self._lock:
            if self._ser and self._ser.is_open:
                try:
                    self._ser.write((text + "\n").encode())
                except Exception as e:
                    self.error_occurred.emit(str(e))

    def send_data_point(self, s1, s2, s3, mode, airspeed, ts):
        """Format and send $AOA + $FLIGHT_MODE + $FLIGHT_PARAMS messages."""
        if s1 is not None and s2 is not None and s3 is not None:
            self.send(f"$AOA,S1={s1:.2f},S2={s2:.2f},S3={s3:.2f},TS={ts}*")
        if mode:
            self.send(f"$FLIGHT_MODE,MODE={mode},TS={ts}*")
        if airspeed is not None:
            self.send(f"$FLIGHT_PARAMS,AIRSPEED={airspeed:.1f},TS={ts}*")

    def request_stop(self):
        self._stop = True

    def run(self):
        self._stop = False
        while not self._stop:
            with self._lock:
                ser = self._ser
            if not ser or not ser.is_open:
                time.sleep(0.05)
                continue
            try:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                self.line_received.emit(line)
                # Parse STATUS= from firmware log
                if "STATUS=" in line:
                    for part in line.split():
                        if part.startswith("STATUS="):
                            self.status_parsed.emit(part.split("=", 1)[1])
                            break
            except Exception:
                time.sleep(0.05)


# ══════════════════════════════════════════════════════════════════════
#  Main Window
# ══════════════════════════════════════════════════════════════════════
class AoAMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AoA Safety Controller")
        self.setMinimumSize(1100, 700)
        self.resize(1200, 750)

        self.processor = AoAProcessor()
        self.streamer = None
        self._is_pilot = True
        self._aoa_history = []
        self._time_history = []
        self._tick = 0
        self._serial_ts = 0

        # Serial worker for ESP32 communication
        self.serial_worker = SerialWorker(self)
        self.serial_worker.line_received.connect(self._on_serial_rx)
        self.serial_worker.status_parsed.connect(self._on_serial_status)
        self.serial_worker.error_occurred.connect(self._on_serial_error)
        self.serial_worker.start()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        root.addLayout(self._build_top_bar())
        mid = QHBoxLayout()
        mid.setSpacing(8)
        mid.addWidget(self._build_mode_panel(), 0)
        mid.addWidget(self._build_animation_panel(), 1)
        mid.addWidget(self._build_right_panel(), 0)
        root.addLayout(mid, 1)
        root.addLayout(self._build_bottom_bar())
        root.addWidget(self._build_serial_panel())

        # Plot config
        self.plot_widget.setBackground(BG_PANEL)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self.plot_widget.setLabel("left", "AoA (°)")
        self.plot_widget.setLabel("bottom", "Sample")
        self.plot_curve = self.plot_widget.plot(
            pen=pg.mkPen(color=ACCENT_CYAN, width=2)
        )
        self.limit_line = pg.InfiniteLine(
            angle=0, pen=pg.mkPen(color=RED, width=1, style=Qt.DashLine)
        )
        self.plot_widget.addItem(self.limit_line)

    # ── Top bar ───────────────────────────────────────────────────────
    def _build_top_bar(self):
        layout = QHBoxLayout()
        layout.setSpacing(10)

        def _field(label_text, placeholder, width=80):
            lbl = QLabel(label_text)
            lbl.setFont(QFont("Inter", 11, QFont.Bold))
            le = QLineEdit()
            le.setPlaceholderText(placeholder)
            le.setFixedWidth(width)
            layout.addWidget(lbl)
            layout.addWidget(le)
            return le

        self.inp_airspeed = _field("AIRSPEED", "kts", 90)
        self.inp_s1 = _field("S1", "°", 70)
        self.inp_s2 = _field("S2", "°", 70)
        self.inp_s3 = _field("S3", "°", 70)

        self.btn_send = QPushButton("▶  SEND")
        self.btn_send.setStyleSheet(
            f"QPushButton {{ background:{ACCENT_BLUE}; color:#fff; font-weight:700; border-radius:6px; padding:8px 22px; }}"
            f"QPushButton:hover {{ background:#6db3ff; }}"
        )
        self.btn_send.clicked.connect(self._on_static_send)
        layout.addWidget(self.btn_send)

        self.btn_reset = QPushButton("↺ RESET")
        self.btn_reset.setStyleSheet(
            f"QPushButton {{ background:{BG_CARD}; color:{TEXT_PRIMARY}; font-weight:700; border-radius:6px; padding:8px 14px; }}"
            f"QPushButton:hover {{ background:{BORDER}; }}"
        )
        self.btn_reset.clicked.connect(self._reset_to_normal)
        layout.addWidget(self.btn_reset)

        layout.addStretch()
        return layout

    # ── Left: Mode panel ──────────────────────────────────────────────
    def _build_mode_panel(self):
        group = QGroupBox("FLIGHT MODE")
        group.setFixedWidth(150)
        vbox = QVBoxLayout()
        vbox.setSpacing(8)
        self.mode_group = QButtonGroup(self)
        modes = ["TAKEOFF", "CLIMB", "CRUISE", "LANDING"]
        self._mode_radios = {}
        for m in modes:
            rb = QRadioButton(m)
            rb.setFont(QFont("Inter", 12))
            self.mode_group.addButton(rb)
            self._mode_radios[m] = rb
            vbox.addWidget(rb)
        self._mode_radios["CRUISE"].setChecked(True)
        vbox.addStretch()
        group.setLayout(vbox)
        return group

    # ── Center: Animation ─────────────────────────────────────────────
    def _build_animation_panel(self):
        group = QGroupBox("FLIGHT VISUALIZATION")
        vbox = QVBoxLayout()
        self.animation = FlightAnimationWidget()
        vbox.addWidget(self.animation)
        group.setLayout(vbox)
        return group

    # ── Right: AoA plot + submode ─────────────────────────────────────
    def _build_right_panel(self):
        group = QGroupBox("AoA SIGNAL")
        group.setFixedWidth(330)
        vbox = QVBoxLayout()
        vbox.setSpacing(8)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setMinimumHeight(200)
        vbox.addWidget(self.plot_widget, 1)

        # Submode TV Display — single readout showing active submode
        sm_frame = QFrame()
        sm_frame.setStyleSheet(
            f"QFrame {{ background: #0a0c12; border: 3px solid {BORDER}; border-radius: 10px; }}"
        )
        sm_inner = QVBoxLayout(sm_frame)
        sm_inner.setContentsMargins(10, 8, 10, 8)
        sm_inner.setSpacing(2)

        sm_title = QLabel("SUBMODE")
        sm_title.setFont(QFont("Inter", 9, QFont.Bold))
        sm_title.setAlignment(Qt.AlignCenter)
        sm_title.setStyleSheet(f"color:{TEXT_DIM}; background:transparent; border:none;")
        sm_inner.addWidget(sm_title)

        self.submode_display = QLabel("NORMAL")
        self.submode_display.setFont(QFont("Inter", 20, QFont.Bold))
        self.submode_display.setAlignment(Qt.AlignCenter)
        self.submode_display.setFixedHeight(48)
        self.submode_display.setStyleSheet(
            f"color:{GREEN}; background: #111520; border: 1px solid #1e2236;"
            f" border-radius: 6px; letter-spacing: 2px;"
        )
        sm_inner.addWidget(self.submode_display)

        vbox.addWidget(sm_frame)

        # AoA readout
        self.lbl_aoa = QLabel("AoA: —")
        self.lbl_aoa.setFont(QFont("Inter", 18, QFont.Bold))
        self.lbl_aoa.setAlignment(Qt.AlignCenter)
        self.lbl_aoa.setStyleSheet(f"color:{ACCENT_CYAN};")
        vbox.addWidget(self.lbl_aoa)

        group.setLayout(vbox)
        return group

    # ── Bottom bar ────────────────────────────────────────────────────
    def _build_bottom_bar(self):
        layout = QHBoxLayout()
        layout.setSpacing(14)

        # Control mode
        ctrl_box = QGroupBox("CONTROL")
        ctrl_lay = QHBoxLayout()
        self.btn_pilot = QPushButton("✈  PILOT")
        self.btn_pilot.setCheckable(True)
        self.btn_pilot.setChecked(True)
        self.btn_autopilot = QPushButton("⚙  AUTOPILOT")
        self.btn_autopilot.setCheckable(True)
        self.btn_pilot.clicked.connect(lambda: self._set_control(True))
        self.btn_autopilot.clicked.connect(lambda: self._set_control(False))
        ctrl_lay.addWidget(self.btn_pilot)
        ctrl_lay.addWidget(self.btn_autopilot)
        self.led = LEDWidget()
        ctrl_lay.addWidget(self.led)
        ctrl_box.setLayout(ctrl_lay)
        layout.addWidget(ctrl_box)

        # Input mode
        mode_box = QGroupBox("INPUT MODE")
        mode_lay = QHBoxLayout()
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Static", "Dynamic (CSV)"])
        self.combo_mode.currentIndexChanged.connect(self._on_mode_switch)
        mode_lay.addWidget(self.combo_mode)

        self.btn_start_csv = QPushButton("▶  START")
        self.btn_start_csv.setStyleSheet(
            f"QPushButton {{ background:{GREEN}; color:#000; font-weight:700; }}"
        )
        self.btn_start_csv.clicked.connect(self._on_start_csv)
        self.btn_start_csv.setEnabled(False)
        mode_lay.addWidget(self.btn_start_csv)

        self.btn_stop_csv = QPushButton("⏹  STOP")
        self.btn_stop_csv.setStyleSheet(
            f"QPushButton {{ background:{RED}; color:#fff; font-weight:700; }}"
        )
        self.btn_stop_csv.clicked.connect(self._on_stop_csv)
        self.btn_stop_csv.setEnabled(False)
        mode_lay.addWidget(self.btn_stop_csv)

        lbl_speed = QLabel("Speed:")
        lbl_speed.setFont(QFont("Inter", 11))
        mode_lay.addWidget(lbl_speed)
        self.slider_speed = QSlider(Qt.Horizontal)
        self.slider_speed.setRange(20, 500)
        self.slider_speed.setValue(150)
        self.slider_speed.setFixedWidth(100)
        self.slider_speed.valueChanged.connect(self._on_speed_change)
        mode_lay.addWidget(self.slider_speed)

        mode_box.setLayout(mode_lay)
        layout.addWidget(mode_box)

        # Threshold info label
        self.lbl_thresholds = QLabel("")
        self.lbl_thresholds.setFont(QFont("Inter", 10))
        self.lbl_thresholds.setStyleSheet(f"color:{TEXT_DIM}; padding: 4px 8px;")
        layout.addWidget(self.lbl_thresholds)
        layout.addStretch()
        return layout

    # ══════════════════════════════════════════════════════════════════
    #  Slots / Handlers
    # ══════════════════════════════════════════════════════════════════
    def _get_selected_mode(self) -> str:
        for m, rb in self._mode_radios.items():
            if rb.isChecked():
                return m
        return "CRUISE"

    def _safe_float(self, text: str):
        try:
            return float(text.strip())
        except (ValueError, AttributeError):
            return None

    @pyqtSlot()
    def _on_static_send(self):
        s1 = self._safe_float(self.inp_s1.text())
        s2 = self._safe_float(self.inp_s2.text())
        s3 = self._safe_float(self.inp_s3.text())
        airspeed = self._safe_float(self.inp_airspeed.text())
        mode = self._get_selected_mode()

        # Reset the estimator so previous state doesn't pollute static results,
        # then run the same input through the pipeline 50 times so the Kalman
        # filter converges to the true steady-state AoA value.
        self.processor.reset()
        CONVERGENCE_ITERS = 50
        for _ in range(CONVERGENCE_ITERS):
            result = self.processor.process_input(s1, s2, s3, mode, airspeed)

        self._apply_result(result)
        self._update_threshold_info(mode)
        # Also send to ESP32 if connected
        self._send_to_esp32(s1, s2, s3, mode, airspeed)

    def _apply_result(self, r: ProcessResult):
        self._tick += 1
        self._aoa_history.append(r.aoa)
        self._time_history.append(self._tick)
        # Keep last 200 samples
        if len(self._aoa_history) > 200:
            self._aoa_history = self._aoa_history[-200:]
            self._time_history = self._time_history[-200:]

        self.plot_curve.setData(self._time_history, self._aoa_history)
        self.limit_line.setValue(r.limit_high)

        self.lbl_aoa.setText(f"AoA: {r.aoa:.2f}°")
        # Use ESP32's submode if connected to prevent UI mismatch/flicker
        active_submode = r.submode
        if self.serial_worker.is_connected and self.chk_send_serial.isChecked():
            active_submode = self.animation.submode

        self.animation.update_state(r.aoa, r.mode, active_submode, r.airspeed)

        # Only use Python simulation submode if we aren't getting terminal data
        if not (self.serial_worker.is_connected and self.chk_send_serial.isChecked()):
            self.led.set_state(r.submode)

            # Submode TV display
            sm_color = SUBMODE_COLORS.get(r.submode, GREEN)
            self.submode_display.setText(r.submode)
            self.submode_display.setStyleSheet(
                f"color:{sm_color}; background: #111520; border: 1px solid #1e2236;"
                f" border-radius: 6px; letter-spacing: 2px;"
            )

            # Lock autopilot on OVERRIDE
            if r.submode == "OVERRIDE":
                self._set_control(True)
                self.btn_autopilot.setEnabled(False)
            else:
                self.btn_autopilot.setEnabled(True)

        # Update mode radio in dynamic mode
        if self.combo_mode.currentIndex() == 1 and r.mode in self._mode_radios:
            self._mode_radios[r.mode].setChecked(True)
            self._update_threshold_info(r.mode)

        # Update input fields in dynamic mode
        if self.combo_mode.currentIndex() == 1:
            self.inp_s1.setText(f"{r.s1:.2f}" if r.s1 is not None else "")
            self.inp_s2.setText(f"{r.s2:.2f}" if r.s2 is not None else "")
            self.inp_s3.setText(f"{r.s3:.2f}" if r.s3 is not None else "")
            self.inp_airspeed.setText(f"{r.airspeed:.1f}" if r.airspeed is not None else "")

    def _set_control(self, pilot: bool):
        self._is_pilot = pilot
        self.btn_pilot.setChecked(pilot)
        self.btn_autopilot.setChecked(not pilot)

    @pyqtSlot(int)
    def _on_mode_switch(self, idx):
        is_dynamic = idx == 1
        self.btn_start_csv.setEnabled(is_dynamic)
        self.btn_send.setEnabled(not is_dynamic)
        for le in [self.inp_s1, self.inp_s2, self.inp_s3, self.inp_airspeed]:
            le.setReadOnly(is_dynamic)
        for rb in self._mode_radios.values():
            rb.setEnabled(not is_dynamic)

    @pyqtSlot()
    def _on_start_csv(self):
        self.processor.reset()
        self._aoa_history.clear()
        self._time_history.clear()
        self._tick = 0

        self.streamer = CSVStreamer(interval_ms=self.slider_speed.value())
        self.streamer.row_ready.connect(self._on_csv_row)
        self.streamer.finished_stream.connect(self._on_csv_done)
        self.streamer.start()
        self.btn_start_csv.setEnabled(False)
        self.btn_stop_csv.setEnabled(True)

    @pyqtSlot()
    def _on_stop_csv(self):
        if self.streamer:
            self.streamer.request_stop()
            self.streamer.wait(2000)
            self.streamer = None
        self.btn_start_csv.setEnabled(True)
        self.btn_stop_csv.setEnabled(False)
        self._reset_to_normal()

    def _reset_to_normal(self):
        """Send a safe data point so ESP32 and UI return to NORMAL state."""
        self.processor.reset()
        result = self.processor.process_input(5.0, 5.0, 5.0, "CRUISE", 200.0)
        self._apply_result(result)
        self._send_to_esp32(5.0, 5.0, 5.0, "CRUISE", 200.0)

    @pyqtSlot(object)
    def _on_csv_row(self, row: CSVRow):
        result = self.processor.process_input(
            row.s1, row.s2, row.s3, row.mode, row.airspeed
        )
        self._apply_result(result)
        # Send to ESP32 dynamically; ts=None ensures we step by slider speed
        self._send_to_esp32(row.s1, row.s2, row.s3, row.mode, row.airspeed, ts=None)

    @pyqtSlot()
    def _on_csv_done(self):
        self.btn_start_csv.setEnabled(True)
        self.btn_stop_csv.setEnabled(False)
        self._reset_to_normal()

    @pyqtSlot(int)
    def _on_speed_change(self, val):
        if self.streamer:
            self.streamer.set_speed(val)

    def _update_threshold_info(self, mode: str):
        """Display the active threshold boundaries for the current flight mode."""
        low, high = self.processor.thresholds.get(
            (self.processor.aircraft_type, mode), (0.0, 20.0)
        )
        caution = high - 2.0
        protection = high - 0.5
        self.lbl_thresholds.setText(
            f"▸ {mode}  limits: CAUTION >{caution:.1f}°  PROTECTION >{protection:.1f}°  OVERRIDE >{high:.1f}°"
        )

    # ══════════════════════════════════════════════════════════════════
    #  Serial Port Panel + Handlers
    # ══════════════════════════════════════════════════════════════════
    def _build_serial_panel(self):
        group = QGroupBox("ESP32 SERIAL PORT")
        hbox = QHBoxLayout()
        hbox.setSpacing(8)

        # Port selector
        lbl_port = QLabel("Port:")
        lbl_port.setFont(QFont("Inter", 11, QFont.Bold))
        hbox.addWidget(lbl_port)

        self.combo_port = QComboBox()
        self.combo_port.setMinimumWidth(200)
        self._refresh_ports()
        hbox.addWidget(self.combo_port)

        self.btn_refresh = QPushButton("⟳")
        self.btn_refresh.setFixedWidth(36)
        self.btn_refresh.clicked.connect(self._refresh_ports)
        hbox.addWidget(self.btn_refresh)

        # Connect button
        self.btn_connect = QPushButton("🔌  CONNECT")
        self.btn_connect.setStyleSheet(
            f"QPushButton {{ background:{ACCENT_BLUE}; color:#fff; font-weight:700; }}"
        )
        self.btn_connect.clicked.connect(self._on_serial_connect)
        hbox.addWidget(self.btn_connect)

        # Send-to-ESP32 checkbox
        self.chk_send_serial = QCheckBox("Send to ESP32")
        self.chk_send_serial.setChecked(True)
        self.chk_send_serial.setStyleSheet(f"color:{TEXT_PRIMARY}; font-size:12px;")
        hbox.addWidget(self.chk_send_serial)

        # Status label
        self.lbl_serial_status = QLabel("⬤ Disconnected")
        self.lbl_serial_status.setFont(QFont("Inter", 10, QFont.Bold))
        self.lbl_serial_status.setStyleSheet(f"color:{RED};")
        hbox.addWidget(self.lbl_serial_status)

        # Serial log
        self.serial_log = QTextEdit()
        self.serial_log.setReadOnly(True)
        self.serial_log.setMaximumHeight(80)
        self.serial_log.document().setMaximumBlockCount(100)
        self.serial_log.setStyleSheet(
            f"background:{BG_CARD}; color:{ACCENT_CYAN}; font-family:monospace;"
            f" font-size:11px; border:1px solid {BORDER}; border-radius:6px;"
        )

        vbox = QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.serial_log)
        group.setLayout(vbox)
        return group

    def _refresh_ports(self):
        self.combo_port.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.combo_port.addItem(f"{p.device}  ({p.description})", p.device)
        # Pre-select usbserial port if found
        for i in range(self.combo_port.count()):
            if "usbserial" in (self.combo_port.itemData(i) or ""):
                self.combo_port.setCurrentIndex(i)
                break

    @pyqtSlot()
    def _on_serial_connect(self):
        if self.serial_worker.is_connected:
            self.serial_worker.close_port()
            self.btn_connect.setText("🔌  CONNECT")
            self.btn_connect.setStyleSheet(
                f"QPushButton {{ background:{ACCENT_BLUE}; color:#fff; font-weight:700; }}"
            )
            self.lbl_serial_status.setText("⬤ Disconnected")
            self.lbl_serial_status.setStyleSheet(f"color:{RED};")
            self.serial_log.append("--- Disconnected ---")
        else:
            port = self.combo_port.currentData()
            if not port:
                self.serial_log.append("ERROR: No port selected")
                return
            ok = self.serial_worker.open_port(port, 115200)
            if ok:
                self.btn_connect.setText("⏏  DISCONNECT")
                self.btn_connect.setStyleSheet(
                    f"QPushButton {{ background:{GREEN}; color:#000; font-weight:700; }}"
                )
                self.lbl_serial_status.setText(f"⬤ {port}")
                self.lbl_serial_status.setStyleSheet(f"color:{GREEN};")
                self.serial_log.append(f"--- Connected to {port} ---")
            else:
                self.serial_log.append(f"ERROR: Could not open {port}")

    @pyqtSlot(str)
    def _on_serial_rx(self, line: str):
        # Filter out redundant log lines from the ESP32's 20ms loop
        # The firmware increments IDX continuously, so we remove it before comparison
        line_no_idx = re.sub(r'IDX=\d+\s*', '', line)
        if hasattr(self, '_last_rx_line_no_idx') and line_no_idx == self._last_rx_line_no_idx:
            return
        self._last_rx_line_no_idx = line_no_idx

        self.serial_log.append(f"RX: {line}")
        # Auto-scroll
        sb = self.serial_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    @pyqtSlot(str)
    def _on_serial_status(self, status: str):
        """Firmware sent back a STATUS= field — update the GUI widgets."""
        self.led.set_state(status)
        
        # Sync the large TV readout to the terminal output
        sm_color = SUBMODE_COLORS.get(status, GREEN)
        self.submode_display.setText(status)
        self.submode_display.setStyleSheet(
            f"color:{sm_color}; background: #111520; border: 1px solid #1e2236;"
            f" border-radius: 6px; letter-spacing: 2px;"
        )
        
        # Sync the flight animation badge
        self.animation.submode = status
        self.animation.update()

        # Handle autopilot lock from terminal status
        if status == "OVERRIDE":
            self._set_control(True)
            self.btn_autopilot.setEnabled(False)
        else:
            self.btn_autopilot.setEnabled(True)

    @pyqtSlot(str)
    def _on_serial_error(self, msg: str):
        self.serial_log.append(f"ERR: {msg}")

    def _send_to_esp32(self, s1, s2, s3, mode, airspeed, ts=None):
        """Send current data point to ESP32 if connected and checkbox enabled."""
        if self.serial_worker.is_connected and self.chk_send_serial.isChecked():
            if ts is not None:
                send_ts = ts
            else:
                # Synchronize timestamp steps with the GUI speed slider in dynamic mode
                step = self.slider_speed.value() if self.combo_mode.currentIndex() == 1 else 20
                self._serial_ts += step
                send_ts = self._serial_ts
            self.serial_worker.send_data_point(s1, s2, s3, mode, airspeed, send_ts)

    def closeEvent(self, event):
        self.serial_worker.request_stop()
        self.serial_worker.close_port()
        self.serial_worker.wait(1000)
        if self.streamer:
            self.streamer.request_stop()
            self.streamer.wait(1000)
        event.accept()


# ── Entry point ───────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(GLOBAL_STYLE)
    window = AoAMainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
