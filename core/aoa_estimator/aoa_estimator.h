#ifndef AOA_ESTIMATOR_H
#define AOA_ESTIMATOR_H

#include <pthread.h>

typedef struct {
    float aoa_validated;
    float confidence;
} AoA_Input;

typedef struct {
    float aoa_final;
    float aoa_rate;
} AoA_Output;

typedef struct {
    float estimate;
    float error_cov;
    float process_noise;
    float measurement_noise;
} KalmanState;

typedef struct {
    KalmanState kf;
    pthread_mutex_t *mutex;
} AoAEstimatorContext;

void AoAEstimator_init(AoAEstimatorContext *ctx, pthread_mutex_t *mutex);

void AoAEstimator_process(AoAEstimatorContext *ctx,
                          AoA_Input *input,
                          AoA_Output *output);

#endif
