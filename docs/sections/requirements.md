# Aircraft Angle-of-Attack (AoA) Safety Controller  

## Stakeholder Requirements

Stakeholders require a system that:
- Maintains aircraft angle-of-attack within safe limits under all operating conditions
- Detects unsafe AoA conditions and intervenes automatically when required
- Handles sensor faults, missing data, and delayed inputs without compromising safety
- Clearly alerts the pilot or autopilot during safety-critical conditions
- Logs safety-critical events for verification, certification, and post-flight analysis

---

## Functional Requirements

### FR-1 Input Acquisition and Validation  
The system shall independently receive, validate, timestamp, and manage angle-of-attack sensor data, flight parameter data, flight mode data, and aircraft configuration data.

### FR-2 Asynchronous Data Handling  
The system shall use the most recently received valid value from each input frame type without waiting for all inputs to arrive simultaneously.

### FR-3 AoA Evaluation  
The system shall continuously evaluate the current angle-of-attack against safe operating limits appropriate to the current flight mode and aircraft configuration.

### FR-4 Sensor Disagreement Resolution  
The system shall select the best two angle-of-attack value when the difference between the three AoA sensor readings exceeds a predefined tolerance α.

### FR-5 Protection Mode Activation  
If angle-of-attack exceeds defined safe limits, the system shall override pilot or autopilot control authority and command corrective actions to drive AoA toward a safe range.

### FR-6 Elevator Control Intervention  
The system shall temporarily assume elevator control whenever validated AoA exceeds the critical safety envelope, either too high or too low.

### FR-7 Protection Mode Exit  
The system shall return control authority to the pilot or autopilot only after AoA has remained within safe limits for a defined stabilization period.

### FR-8 Alarm Notification  
The system shall trigger a persistent critical alarm whenever AoA exceeds aircraft-specific safety thresholds.

### FR-9 Event Logging  
The system shall log all safety-critical events, including sensor faults, control authority transitions, and protection mode activations, with timestamps.

---

## Non-Functional Requirements

- **Timing:**  
  Input frames with timestamps older than a defined threshold X milliseconds shall be invalidated, and missing inputs shall be detected using the system-on-chip (SoC) clock.

- **Safety:**  
  The system shall transition to a defined fail-safe mode that prioritizes AoA protection upon detection of critical internal faults or unavailable required inputs.

- **Reliability:**  
  The system shall operate correctly with independent, asynchronous UART inputs that may be delayed, noisy, malformed, or temporarily unavailable.

- **Data Integrity:**  
  Only validated and time-current input data shall be allowed to influence AoA safety decisions.

- **Maintainability:**  
  The system shall be modular, testable, and structured to allow systematic updates and verification.

- **Traceability:**  
  All safety-critical decisions and state transitions shall be traceable through timestamped logs.

---
