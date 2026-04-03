#define _POSIX_C_SOURCE 200809L
#include "flight_control_fsm.h"

#include <stdio.h>
#include <string.h>
#include <semaphore.h>

/* ── Run-loop externs (provided by integration layer) ── */
extern AoA_Output       estimated_output;
extern pthread_mutex_t  estimator_mutex;
extern sem_t            estimated_sem;
extern FlightMode       mode;
extern pthread_mutex_t  sensor_mutex;



static const char *mode_to_phase_name(FlightMode mode)
{
    switch (mode) {
        case MODE_TAKEOFF: return "takeoff";
        case MODE_CRUISE:  return "cruise";
        case MODE_LANDING: return "landing";
        default:           return "cruise";
    }
}



int FlightFSM_init(FlightFSMContext *ctx, pthread_mutex_t *mutex, const char *csv_path)
{
    ctx->mutex           = mutex;
    ctx->phase_count     = 0;
    ctx->current_state   = FSM_NORMAL;
    ctx->current_thresholds.aoa_low  = 3.0f;
    ctx->current_thresholds.aoa_high = 12.0f;

    FILE *fp = fopen(csv_path, "r");
    if (!fp) {
        fprintf(stderr, "[FSM] ERROR: Cannot open CSV '%s'\n", csv_path);
        return -1;
    }

    char line[128];
    /* Skip header */
    if (!fgets(line, sizeof(line), fp)) { fclose(fp); return -1; }

    while (fgets(line, sizeof(line), fp) && ctx->phase_count < MAX_FLIGHT_PHASES) {
        PhaseThresholdEntry *e = &ctx->phase_table[ctx->phase_count];
        if (sscanf(line, "%31[^,],%f,%f",
                   e->phase_name,
                   &e->thresholds.aoa_low,
                   &e->thresholds.aoa_high) == 3) {
            ctx->phase_count++;
        }
    }

    fclose(fp);
    printf("[FSM] Loaded %d threshold entries from '%s'\n", ctx->phase_count, csv_path);
    return 0;
}


Thresholds FlightFSM_get_thresholds_for_mode(FlightFSMContext *ctx, FlightMode mode)
{
    const char *target = mode_to_phase_name(mode);
    for (int i = 0; i < ctx->phase_count; i++) {
        if (strcmp(ctx->phase_table[i].phase_name, target) == 0)
            return ctx->phase_table[i].thresholds;
    }
    fprintf(stderr, "[FSM] WARNING: No thresholds for mode '%s'. Using defaults.\n", target);
    Thresholds def = {3.0f, 12.0f};
    return def;
}



FSM_State FlightFSM_transition_logic(float aoa, Thresholds t)
{
    if (aoa > t.aoa_high)       return FSM_PROTECTION;
    else if (aoa >= t.aoa_low)  return FSM_WARNING;
    else                        return FSM_NORMAL;
}



void FlightFSM_process(FlightFSMContext *ctx, AoA_Output *input, FlightMode mode)
{
    Thresholds t     = FlightFSM_get_thresholds_for_mode(ctx, mode);
    FSM_State  state = FlightFSM_transition_logic(input->aoa_final, t);

    pthread_mutex_lock(ctx->mutex);
    ctx->current_state      = state;
    ctx->current_thresholds = t;
    pthread_mutex_unlock(ctx->mutex);
}



FSM_State FlightFSM_get_state(FlightFSMContext *ctx)
{
    pthread_mutex_lock(ctx->mutex);
    FSM_State s = ctx->current_state;
    pthread_mutex_unlock(ctx->mutex);
    return s;
}

Thresholds FlightFSM_get_thresholds(FlightFSMContext *ctx)
{
    pthread_mutex_lock(ctx->mutex);
    Thresholds t = ctx->current_thresholds;
    pthread_mutex_unlock(ctx->mutex);
    return t;
}



void *fsm_run_loop(void *arg)
{
    FlightFSMContext *ctx = (FlightFSMContext *)arg;

    printf("[FSM] Thread started. Processing 500 frames...\n");

    for (int frame = 0; frame < 500; frame++) {

        sem_wait(&estimated_sem);

        pthread_mutex_lock(&estimator_mutex);
        AoA_Output input = estimated_output;
        pthread_mutex_unlock(&estimator_mutex);

        pthread_mutex_lock(&sensor_mutex);
        FlightMode current_mode = mode;
        pthread_mutex_unlock(&sensor_mutex);

        FlightFSM_process(ctx, &input, current_mode);

        const char *state_str[] = {"NORMAL", "WARNING", "PROTECTION"};
        printf("[FSM] Frame %3d | AoA=%6.2f | Rate=%6.3f | Phase=%-8s | State=%s\n",
               frame + 1, input.aoa_final, input.aoa_rate,
               mode_to_phase_name(current_mode),
               state_str[FlightFSM_get_state(ctx)]);
    }

    printf("[FSM] Thread finished 500 frames.\n");
    return NULL;
}