#ifndef COMMON_TYPES_H
#define COMMON_TYPES_H

typedef enum {
    FSM_NORMAL     = 0,
    FSM_WARNING    = 1,
    FSM_PROTECTION = 2
} FSM_State;

typedef enum {
    MODE_TAKEOFF = 0,
    MODE_CRUISE  = 1,
    MODE_LANDING = 2,
    MODE_UNKNOWN = 3
} FlightMode;

typedef struct {
    float aoa_low;
    float aoa_high;
} Thresholds;

#endif /* COMMON_TYPES_H */
