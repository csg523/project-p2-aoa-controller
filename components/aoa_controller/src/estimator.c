#include "estimator.h"
#include <esp_log.h>
#include <math.h>

static const char *TAG = "ESTIMATOR";
static kalman_state_t kalman_state = {0};

#define TOTAL_SENSORS 3.0f
#define EPSILON 1.0f   // to avoid division by zero

void estimator_init(void) {
    kalman_state.estimated_aoa = 0.0f;
    kalman_state.estimated_variance = 1.0f;
    ESP_LOGI(TAG, "Estimator initialized");
}

float perform_weighted_fusion(validator_result_t *vr) {
    if (!vr || vr->num_valid_sensors == 0) return 0.0f;

    float weights[3] = {0};
    float sum_weights = 0.0f;

    float err1 = fabsf(vr->sensor1_value - vr->median_aoa);
    float err2 = fabsf(vr->sensor2_value - vr->median_aoa);
    float err3 = fabsf(vr->sensor3_value - vr->median_aoa);
    
    if (vr->sensor1_valid) {
        weights[0] = 1.0f / (err1 + EPSILON);
        sum_weights += weights[0];
    }

    if (vr->sensor2_valid) {
        weights[1] = 1.0f / (err2 + EPSILON);
        sum_weights += weights[1];
    }

    if (vr->sensor3_valid) {
        weights[2] = 1.0f / (err3 + EPSILON);
        sum_weights += weights[2];
    }

    float fused = 0.0f;

    if (vr->sensor1_valid)
        fused += (weights[0] / sum_weights) * vr->sensor1_value;

    if (vr->sensor2_valid)
        fused += (weights[1] / sum_weights) * vr->sensor2_value;

    if (vr->sensor3_valid)
        fused += (weights[2] / sum_weights) * vr->sensor3_value;

    return fused;
}

void apply_kalman_filter(float measurement, kalman_state_t *kstate) {
    if (!kstate) return;

    float P = kstate->estimated_aoa;
    float K = 0.0f;

    K = (kstate->estimated_variance > 0.5f) ? (2.0f / TOTAL_SENSORS) : (3.0f / TOTAL_SENSORS);


    kstate->estimated_aoa = P + K * (measurement - P);

    kstate->estimated_variance *= (1.0f - K);
}

void estimator_run(validator_result_t *validator_result, estimator_state_t *estimator_state) {
    if (!estimator_state) return;

    estimator_state->fused_aoa = perform_weighted_fusion(validator_result);

    apply_kalman_filter(estimator_state->fused_aoa, &kalman_state);

    estimator_state->final_calculated_aoa = kalman_state.estimated_aoa;
    estimator_state->is_initialized = true;

    ESP_LOGD(TAG, "Estimation AOA=%.2f", estimator_state->final_calculated_aoa);
}
