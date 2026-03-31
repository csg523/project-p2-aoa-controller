#include "aoa_estimator.h"

void Kalman_Init(KalmanState_t *state) {
    state->estimate = 0.0f;
    state->error_covariance = 1.0f;
    state->process_noise = 0.01f;
    state->measurement_noise = 0.1f;
}

float Kalman_Update(KalmanState_t *state, float measurement) {

    // Prediction
    float pred_est = state->estimate;
    float pred_cov = state->error_covariance + state->process_noise;

    // Kalman gain
    float K = pred_cov / (pred_cov + state->measurement_noise);

    // Update
    state->estimate = pred_est + K * (measurement - pred_est);
    state->error_covariance = (1 - K) * pred_cov;

    return state->estimate;
}
