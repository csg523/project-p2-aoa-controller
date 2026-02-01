## System Boundary

### Inside the System
- Parses independent asynchronous UART frames for AoA, flight parameters, and flight mode data.
- Evaluates current AoA against safety envelopes that vary by flight mode, airspeed, and aircraft type
- Manages control authority transitions between Normal,Warning and Protection
- Motor actuation commands
- Logging of infusion and fault events

### Outside the System
- AoA sensors (S1, S2)
- Flight Mode 
- Flight Parameter (Airspeed)
- Pilot
- Autopilot

### Assumptions
- Sensor data is provided periodically and asynchronously
- Aircraft configuration (A or B) is loaded at startup and remains fixed
- Uninterrupted power supply


---

## System Context

### Actors and Interfaces

| Actor / Entity | Type | Interface Description |
|---------------|------|-----------------------|
| AoA Sensor 1 and 2  | Sensors | AoA measurement |
| Airspeed Sensor | Sensor | Transmits current airspeed |
| Flight Mode Source | System | Transmits current flight mode (TAKEOFF / CLIMB / CRUISE / LANDING)  |
| Aircraft Conguration | System | Selects Aircraft A or Aircraft B  |
| Maintenance Logger | System | Fault and safety event recording |


---

### System Context Diagram

```mermaid
flowchart LR
    Pilot -->|Manual inputs / Acknowledge| AoA_System
    AoA1[AoA Sensor S1] -->|AoA Data| AoA_System
    AoA2[AoA Sensor S2] -->|AoA Data| AoA_System
    AirData[Flight Param] -->|Airspeed| AoA_System
    Phase[Flight Mode] -->|Takeoff / climb / cruise / landing| AoA_System
    Config[Aircraft Configuration] -->|A or B| AoA_System

    AoA_System -->|Warnings| Pilot
    AoA_System -->|Autopilot commands| Auto[Autopilot System]
    AoA_System -->|Fault logs| Logger[Maintenance Logger]
```

## Selected Use Cases

| ID   | Use Case          | Actor            | Description                                      |
| ---- | ----------------- | ---------------- | ------------------------------------------------ |
| UC-1 | Monitor AoA    | AoA Sensors        | Continuously monitor and validate AoA         |
| UC-2 | Issue Warning     | System        | Warn pilot when unsafe AoA is detected          |
| UC-3 | Handle Sensor Failure | Sensors  | Detect sensor disagreement or failure         |

---

### Use Case Descriptions

#### UC-1: Monitor AoA
- Goal: Maintain a reliable AoA estimate.
- Trigger: Periodic sensor updates.
- Main Interaction: Validate sensors → compute AoA_EFFECTIVE.
- Outcome: AoA is continuously available or marked UNKNOWN.

#### UC-2: Issue Warning
- Goal: Alert pilot of unsafe AoA.
- Trigger: AoA exceeds phase-specific threshold.
- Main Interaction: Raise visual/aural alert → start response timer.
- Outcome: Pilot responds or system escalates.

#### UC-3: Handle Sensor Failure
- Goal: Maintain safety despite sensor faults.
- Trigger: Sensor stale, missing, or disagreeing.
- Main Interaction: Switch to conservative AoA selection or UNKNOWN state.
- Outcome: Warnings or emergency handling activated.

#### UC-4: Handle Power Loss
- Goal: Ensure patient safety during unexpected power loss.
- Trigger: Loss of external power.
- Main Interaction: Immediately stop infusion; system resets on power restoration.
- Outcome: System enters Safe_Stop state and does not resume infusion automatically.

---

## UML Statechart (Behavioral Model)
```mermaid
stateDiagram-v2
    [*] --> System

    state System {
        state AoA_Calculator {
            [*] --> ReadingSensors

            state ReadingSensors {
                [*] --> SensorsAgree

                SensorsAgree --> SensorsDisagree: |S1 - S2| > DISAGREE_THRESHOLD
                SensorsDisagree --> SensorsAgree: |S1 - S2| < DISAGREE_CLEAR

                SensorsAgree --> SensorFailed: One sensor stale or missing
                SensorFailed --> SensorsAgree: Failed sensor recovers

            }

            state BothFailed {
                [*] --> NoData
                NoData --> ReadingSensors: Any sensor recovers
            }
        }

        state FlightControl {
            [*] --> TAKEOFF

            state TAKEOFF {
                [*] --> TK_Normal

                TK_Normal --> TK_Warning: AoA > TK_PROTECT_UPPER
                TK_Warning --> TK_Normal: Pilot responds within 5s
                TK_Warning --> TK_Protection: No response in 5s
                TK_Protection --> TK_Normal: AoA back to safe
            }

            TAKEOFF --> CLIMB: Flight_Mode Changed

            state CLIMB {
                [*] --> CL_Normal

                CL_Normal --> CL_Warning: AoA > CL_PROTECT_UPPER
                CL_Warning --> CL_Normal: Pilot responds within 5s
                CL_Warning --> CL_Protection: No response in 5s
                CL_Protection --> CL_Normal: AoA back to safe
            }

            CLIMB --> CRUISE: Flight_Mode Changed

            state CRUISE {
                [*] --> CR_Autopilot

                state CR_Autopilot {
                    [*] --> CR_AP_Normal

                    CR_AP_Normal --> CR_AP_Warning: AoA > CR_PROTECT_UPPER
                    CR_AP_Warning --> CR_AP_Normal: Autopilot corrects within 5s
                    CR_AP_Warning --> CR_Pilot: No correction in 5s → FORCE to Pilot
                }

                state CR_Pilot {
                    [*] --> CR_PL_Normal

                    CR_PL_Normal --> CR_PL_Warning: AoA > CR_PROTECT_UPPER
                    CR_PL_Warning --> CR_PL_Normal: Pilot responds within 5s
                    CR_PL_Warning --> CR_Autopilot: No response in 5s → FORCE to Autopilot
                }

                CR_Autopilot --> CR_Pilot: Pilot takes manual control
                CR_Pilot --> CR_Autopilot: Pilot engages autopilot
            }

            CRUISE --> LANDING: Flight_Mode Changed

            state LANDING {
                [*] --> LD_Normal

                LD_Normal --> LD_Warning: AoA > LD_PROTECT_UPPER
                LD_Warning --> LD_Normal: Pilot responds within 5s
                LD_Warning --> LD_Protection: No response in 5s
                LD_Protection --> LD_Normal: AoA back to safe
            }

            LANDING --> CLIMB: Go-around detected
        }
    }

    note right of AoA_Calculator
        Output: AoA_EFFECTIVE
        ─────────────────────
        SensorsAgree:
          AoA_EFFECTIVE = avg(S1, S2)
        SensorsDisagree:
          AoA_EFFECTIVE = max(S1, S2)
          (conservative — assume worst)
        SensorFailed:
          AoA_EFFECTIVE = valid sensor only
        BothFailed:
          AoA_EFFECTIVE = UNKNOWN
          (trigger emergency)
    end note

    note right of FlightControl
        Pilot-only phases:
        ─────────────────
        Normal → Warning (5s timer)
          Responded?  → Normal
          No response? → Protection
          AoA fixed   → Normal

        Cruise (Pilot + Autopilot):
        ─────────────────────────
        Normal → Warning (5s timer)
          Responded?  → Normal
          No response? → FORCE switch
            to the other mode

        Configurable variables:
          TK_PROTECT_UPPER
          CL_PROTECT_UPPER
          CR_PROTECT_UPPER
          LD_PROTECT_UPPER
    end note
```

---
## Safety and Error Handling (Behavioral View)
- Safety events override normal operation.
- AoA UNKNOWN forces degraded or emergency handling.
- All safety-critical events are logged for traceability.
- Protection authority depends on aircraft configuration.
- Pilot always retains override capability.

## Change Log
| Date | Change          | Author  |
| ---- | --------------- | ------- | 
|   01/02/2026   | Initial version | Project Team |