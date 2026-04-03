#include "aoa_estimator.h"

static float kalman_update(KalmanState *kf, float measurement) {
    // Prediction step
    float pred_estimate = kf->estimate;
    float pred_cov = kf->error_cov + kf->process_noise;

    // Update step
    float K = pred_cov / (pred_cov + kf->measurement_noise);

    kf->estimate = pred_estimate + K * (measurement - pred_estimate);
    kf->error_cov = (1 - K) * pred_cov;

    return kf->estimate;
}

void AoAEstimator_init(AoAEstimatorContext *ctx, pthread_mutex_t *mutex) {
    ctx->mutex = mutex;

    ctx->kf.estimate = 0.0;
    ctx->kf.error_cov = 1.0;
    ctx->kf.process_noise = 0.1;
    ctx->kf.measurement_noise = 0.5;
}

void AoAEstimator_process(AoAEstimatorContext *ctx,
                          AoA_Input *input,
                          AoA_Output *output) {

    pthread_mutex_lock(ctx->mutex);

    // Weighted fusion (confidence-based)
    float weighted_aoa = input->aoa_validated * input->confidence;

    // Kalman filter
    float filtered_aoa = kalman_update(&ctx->kf, weighted_aoa);

    // Rate estimation
    float aoa_rate = filtered_aoa - ctx->kf.estimate;

    output->aoa_final = filtered_aoa;
    output->aoa_rate = aoa_rate;

    pthread_mutex_unlock(ctx->mutex);
}
