[![Open in Codespaces](https://classroom.github.com/assets/launch-codespace-2972f46106e565e64193e422d61a12cf1da4916b45550586e14ef0a7c637dd04.svg)](https://classroom.github.com/open-in-codespaces?assignment_repo_id=22326811)
# CS G523 – Capstone Project  
## p2-aoa-controller – Aircraft Angle-of-Attack (AoA) Safety Controller  
**(UART-Simulated Inputs, Independent Data Sources)**

---

## 1. Problem Statement / Specification

Design and implement an **embedded safety controller for managing aircraft angle-of-attack (AoA)**.

The system receives **two independent AoA sensor values** and determines whether the aircraft can continue to be controlled by the **pilot or autopilot**, or whether **automatic AoA-based intervention** is required to prevent unsafe flight conditions.

The system shall:
- Continuously monitor two AoA sensor inputs
- Determine whether the current AoA is within safe operating limits
- Allow pilot or autopilot control when AoA is safely within limits
- Detect when AoA is **approaching unsafe or critical limits**
- Temporarily override pilot/autopilot input and command elevator deflections to drive AoA back into a safe range
- Handle both **high AoA (stall risk)** and **low AoA (loss-of-lift / overspeed risk)** conditions
- Resolve disagreements or faults in AoA sensor inputs conservatively

All safety-critical decisions must be made **locally and deterministically**.

---

## 2. Motivation and Context

Angle-of-attack is a fundamental parameter governing aircraft safety.

Unsafe AoA conditions can lead to:
- aerodynamic stall (excessively high AoA)
- loss of lift or excessive structural loads (excessively low AoA at high speed)

Modern aircraft rely on **software-mediated flight control laws** to ensure AoA remains within safe bounds across different operating regimes.

This project focuses on the **embedded software responsible for AoA-based protection and control authority management**, not on aerodynamics or flight dynamics modeling.

---

## 3. System Boundary

### In Scope
- Embedded software responsible for:
  - Receiving AoA sensor data and flight context data
  - Evaluating AoA safety margins
  - Managing control authority between pilot/autopilot and AoA protection logic
  - Generating elevator control commands during protection modes
  - Handling sensor disagreement, missing data, and abnormal inputs

### Out of Scope
- Physical AoA sensor design
- Aircraft flight dynamics simulation
- Actuator hardware design
- Human–machine interface design
- Cloud-based or remote control logic

---

## 4. Input Specification (UART-Based Simulation)

### Rationale for Independent UART Frames

All inputs are provided via **UART-based simulation**, but **as independent frame streams**, mimicking:
- independent sensors,
- independent avionics subsystems,
- and independent interrupt sources.

This forces the software to reason about **asynchronous, partially updated system state**.

---

### 4.1 AoA Sensor Frames

- Two independent AoA values are provided
- Frames may:
  - arrive at different rates
  - be delayed, missing, noisy, or malformed

**Example frame**
```
$AOA,
S1=12.4,
S2=12.9,
TS=345678
*
```

---

### 4.2 Flight Parameter Frames

Flight parameters relevant to AoA safety include:
- airspeed
- other scalar parameters relevant to envelope computation

These parameters are provided **independently** of AoA frames.

**Example frame**
```
$FLIGHT_PARAMS,
AIRSPEED=210,
TS=345679
*
```

---

### 4.3 Flight Mode Frames

The current flight mode is provided independently as a discrete input:
- takeoff
- climb
- cruise
- landing

**Example frame**
```
$FLIGHT_MODE,
MODE=CRUISE,
TS=345680
*
```

---

### 4.4 Aircraft Configuration

Aircraft-specific behavior is selected via configuration:
- **Aircraft A**
- **Aircraft B**

All aircraft-specific parameters, including those related to weight or structural limits, are assumed to be encapsulated within the selected configuration.

---

## 5. AoA Safety Envelope (Conceptual)

The system must determine whether the current AoA lies within a **mode- and aircraft-dependent safe envelope**.

Key expectations:
- Safe AoA limits vary with airspeed
- Different flight modes have different safety margins
- Different aircraft configurations have different envelopes

Exact numerical limits are **intentionally not specified** and must be derived, justified, and documented by the project team.

---

## 6. Control Authority Logic

At a high level, the system operates in one of the following conceptual regimes:

- **Normal Control**
  - Pilot or autopilot commands elevators directly
  - AoA is comfortably within safe limits

- **Protection Active**
  - Control authority shifts to AoA protection logic
  - Elevator commands are generated to drive AoA back toward safe values

- **Recovery / Exit**
  - AoA has returned to a safe region
  - Control authority is gradually returned to pilot/autopilot

Precise logic, transitions, and timing are to be **designed and justified by the team**.

---

## 7. Safety Expectations (Intentionally High-Level)

At a high level, the AoA controller is expected to:
- Prevent sustained operation outside the safe AoA envelope
- Act conservatively under sensor disagreement or stale data
- Avoid abrupt or oscillatory control behavior
- Fail in a predictable and safe manner under abnormal inputs
- Never amplify unsafe pilot commands

The system must clearly define:
- how asynchronous inputs are synchronized or validated
- how stale data is detected and handled
- how and when control authority is returned

---

## 8. What Is Intentionally Not Provided

The following are deliberately not specified:
- Exact AoA thresholds or numerical limits
- Sensor fusion or voting algorithms
- Control law equations
- State machine definitions
- Timing constants and hysteresis values

Teams are expected to:
- derive detailed requirements from the problem statement
- propose and justify an event-driven control architecture
- define conservative safety policies
- validate behavior using systematic asynchronous test cases

---

## 9. Expected Outcome

By the end of the project, teams should be able to demonstrate:
- A working AoA safety controller
- Correct switching of control authority under unsafe conditions
- Robust handling of asynchronous and partial input updates
- Clear dependence of behavior on flight mode and aircraft configuration
- Deterministic and well-justified safety behavior

---

**Note:** The use of independent UART frames is deliberate and mirrors real avionics systems where sensor and mode information arrive asynchronously.  
Projects will be evaluated on **software robustness, event-driven reasoning, and safety discipline**, not on flight dynamics accuracy.
