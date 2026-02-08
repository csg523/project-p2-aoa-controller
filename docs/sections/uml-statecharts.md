## System Boundary

### Inside the System
- Parses independent asynchronous UART frames for AoA, flight parameters, and flight mode data.
- Evaluates current AoA against safety envelopes that vary by flight mode, airspeed, and aircraft type
- Manages control authority transitions between Normal,Warning and Protection
- Motor actuation commands
- Logging of infusion and fault events

### Outside the System
- AoA sensors (S1, S2, S3)
- Flight Mode 
- Flight Parameter (Airspeed)
- Pilot
- Autopilot

### Assumptions
- Sensor data is provided periodically and asynchronously
- Aircraft configuration (A or B) is loaded at startup and remains fixed
- Uninterrupted power supply
- Constant Air Density 


---

## System Context

### Actors and Interfaces

| Actor / Entity | Type | Interface Description |
|---------------|------|-----------------------|
| AoA Sensor 1, 2 and 3   | Sensors | AoA measurement |
| Airspeed Sensor | Sensor | Transmits current airspeed |
| Flight Mode Source | System | Transmits current flight mode (TAKEOFF / CLIMB / CRUISE / LANDING)  |
| Aircraft Conguration | System | Selects Aircraft A or Aircraft B  |
| Maintenance Logger | System | Fault and safety event recording |


---

### System Context Diagram

```mermaid
flowchart LR
    AoA1[AoA Sensor S1] -->|AoA Data| AoA_System
    AoA2[AoA Sensor S2] -->|AoA Data| AoA_System
    AoA3[AoA Sensor S3] -->|AoA Data| AoA_System
    AirData[Flight Param] -->|Airspeed| AoA_System
    Phase[Flight Mode] -->|Takeoff / climb / cruise / landing| AoA_System
    Config[Aircraft Configuration] -->|A or B| AoA_System

    AoA_System -->|Warnings| Auto[Pilot / Autopilot System]
    AoA_System -->|Pilot / Autopilot commands| Auto[Pilot / Autopilot System]
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

            SensorsAgree --> SensorsDisagree : Sensor difference exceeds threshold

            SensorsDisagree --> SensorsAgree : abs(S1-S2) <= DISAGREE_CLEAR

            SensorsAgree --> SensorFailed : sensor_stale_or_missing

            SensorFailed --> SensorsAgree : sensor_recovered

            SensorsDisagree --> Failed : disagree_timeout

            SensorFailed --> Failed : remaining_sensor_failed
        }
    }

        state FlightControl {
            [*] --> TAKEOFF

            state TAKEOFF {
                [*] --> TK_Normal

                TK_Normal --> TK_Caution : AoA approaching to stall or too low 
                TK_Caution --> TK_Protection : almost stalling or overspeeding
                TK_Protection --> TK_Override : stall is happening
                TK_Override --> TK_Normal : AoA return to safe state 
                TK_Protection --> TK_Caution 
                TK_Caution --> TK_Normal
            }

            TAKEOFF --> CLIMB : Flight_Mode_Changed

            state CLIMB {
                [*] --> CL_Normal

                CL_Normal --> CL_Caution : AoA approaching to stall or too low 
                CL_Caution --> CL_Protection : almost stalling or overspeeding
                CL_Protection --> CL_Override : stall is happening
                CL_Override --> CL_Normal : AoA return to safe state 
                CL_Protection --> CL_Caution 
                CL_Caution --> CL_Normal
            }

            CLIMB --> CRUISE : Flight_Mode_Changed

            state CRUISE {
                [*] --> CR_Normal

                CR_Normal --> CR_Caution : AoA approaching to stall or too low 
                CR_Caution --> CR_Protection : almost stalling or overspeeding
                CR_Protection --> CR_Override : stall is happening
                CR_Override --> CR_Normal : AoA return to safe state 
                CR_Protection --> CR_Caution 
                CR_Caution --> CR_Normal

            }

            CRUISE --> LANDING : Flight_Mode_Changed

            state LANDING {
                [*] --> LD_Normal

                LD_Normal --> LD_Caution : AoA approaching to stall or too low 
                LD_Caution --> LD_Protection : almost stalling or overspeeding
                LD_Protection --> LD_Override : stall is happening
                LD_Override --> LD_Normal : AoA return to safe state 
                LD_Protection --> LD_Caution 
                LD_Caution --> LD_Normal
            }

            LANDING --> CLIMB : go_around_detected
        }
    }
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
