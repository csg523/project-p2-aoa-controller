#define _POSIX_C_SOURCE 200809L
#include "elevator_cmd.h"

#include <stdio.h>
#include <math.h>
#include <time.h>

/* ── Run-loop externs (provided by integration layer) ── */
extern AoA_Output       estimated_output;
extern pthread_mutex_t  estimator_mutex;

/* Forward declarations for FlightFSM getters */
#include "../flight_fsm/flight_control_fsm.h"
extern FlightFSMContext fsm_ctx;



static float clamp(float val, float min_val, float max_val)
{
    if (val < min_val) return min_val;
    if (val > max_val) return max_val;
    return val;
}


void ElevatorCmd_init(ElevatorCmdContext *ctx, pthread_mutex_t *mutex)
{
    ctx->mutex         = mutex;
    ctx->last_elevator = 0.0f;
}



float ElevatorCmd_process(ElevatorCmdContext *ctx, FSM_State state,
                          AoA_Output *input, Thresholds thresholds)
{
    float cmd;

    if (state == FSM_PROTECTION) {
        float excess = input->aoa_final - thresholds.aoa_high;
        if (excess < 0.0f) excess = 0.0f;
        cmd = clamp(-(PROTECTION_GAIN * excess), ELEVATOR_MAX_DOWN, ELEVATOR_MAX_UP);
    } else if (state == FSM_WARNING) {
        cmd = PILOT_AUTHORITY_WARNING;
    } else {
        cmd = PILOT_AUTHORITY_NORMAL;
    }

    pthread_mutex_lock(ctx->mutex);
    ctx->last_elevator = cmd;
    pthread_mutex_unlock(ctx->mutex);

    return cmd;
}


float ElevatorCmd_get_last(ElevatorCmdContext *ctx)
{
    pthread_mutex_lock(ctx->mutex);
    float v = ctx->last_elevator;
    pthread_mutex_unlock(ctx->mutex);
    return v;
}



void *elevator_run_loop(void *arg)
{
    ElevatorCmdContext *ctx = (ElevatorCmdContext *)arg;

    printf("[ELEV] Thread started.\n");

    const char *state_str[] = {"NORMAL", "WARNING", "PROTECTION"};

    for (int frame = 0; frame < 500; frame++) {

        FSM_State  state  = FlightFSM_get_state(&fsm_ctx);
        Thresholds thresh = FlightFSM_get_thresholds(&fsm_ctx);

        pthread_mutex_lock(&estimator_mutex);
        AoA_Output input = estimated_output;
        pthread_mutex_unlock(&estimator_mutex);

        float cmd = ElevatorCmd_process(ctx, state, &input, thresh);

        printf("[ELEV] Frame %3d | State=%-10s | AoA=%6.2f | ElevCmd=%+.2f deg\n",
               frame + 1, state_str[state], input.aoa_final, cmd);

        struct timespec ts = {0, 500000L};
        nanosleep(&ts, NULL);
    }

    printf("[ELEV] Thread finished 500 frames.\n");
    return NULL;
}