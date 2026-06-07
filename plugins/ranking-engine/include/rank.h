#ifndef RANK_H
#define RANK_H

#ifdef __cplusplus
extern "C" {
#endif

void run_parallel_reduction(const float *h_input, float *h_output, int num_elements);

#ifdef __cplusplus
}
#endif

#endif
