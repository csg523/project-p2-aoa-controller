#ifndef ELEVATOR_CMD_H
#define ELEVATOR_CMD_H

#include <pthread.h>
#include "../common/common_types.h"
#include "../aoa_estimator/aoa_estimator.h"

#define ELEVATOR_MAX_UP       25.0f
#define ELEVATOR_MAX_DOWN    -25.0f
#define PILOT_AUTHORITY_NORMAL    0.0f
#define PILOT_AUTHORITY_WARNING  -5.0f
#define PROTECTION_GAIN           2.5f

typedef struct {
    float            last_elevator;
    pthread_mutex_t *mutex;
} ElevatorCmdContext;

void  ElevatorCmd_init(ElevatorCmdContext *ctx, pthread_mutex_t *mutex);
float ElevatorCmd_process(ElevatorCmdContext *ctx, FSM_State state, AoA_Output *input, Thresholds thresholds);
float ElevatorCmd_get_last(ElevatorCmdContext *ctx);

void *elevator_run_loop(void *arg);

#endif 