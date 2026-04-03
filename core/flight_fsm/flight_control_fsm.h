#ifndef FLIGHT_CONTROL_FSM_H
#define FLIGHT_CONTROL_FSM_H

#include <pthread.h>
#include "../common/common_types.h"
#include "../aoa_estimator/aoa_estimator.h"

#define THRESHOLDS_CSV_PATH  "config/thresholds.csv"
#define MAX_FLIGHT_PHASES    16
#define PHASE_NAME_LEN       32

typedef struct {
    char       phase_name[PHASE_NAME_LEN];
    Thresholds thresholds;
} PhaseThresholdEntry;

typedef struct {
    PhaseThresholdEntry phase_table[MAX_FLIGHT_PHASES];
    int                 phase_count;
    FSM_State           current_state;
    Thresholds          current_thresholds;
    pthread_mutex_t    *mutex;
} FlightFSMContext;

int        FlightFSM_init(FlightFSMContext *ctx, pthread_mutex_t *mutex, const char *csv_path);
void       FlightFSM_process(FlightFSMContext *ctx, AoA_Output *input, FlightMode mode);
FSM_State  FlightFSM_get_state(FlightFSMContext *ctx);
Thresholds FlightFSM_get_thresholds(FlightFSMContext *ctx);

/* Pure transition logic — no side-effects, fully testable */
FSM_State  FlightFSM_transition_logic(float aoa, Thresholds t);
Thresholds FlightFSM_get_thresholds_for_mode(FlightFSMContext *ctx, FlightMode mode);

void *fsm_run_loop(void *arg);

#endif 