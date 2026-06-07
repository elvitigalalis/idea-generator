#include "rank.h"

#include <algorithm>
#include <mutex>
#include <thread>
#include <vector>

namespace {

unsigned int worker_count_for(int num_elements) {
    const unsigned int detected = std::thread::hardware_concurrency();
    const unsigned int hardware_workers = detected == 0 ? 1 : detected;
    const unsigned int element_count = static_cast<unsigned int>(std::max(num_elements, 1));
    return std::max(1U, std::min(hardware_workers, element_count));
}

float reduce_chunk(const float *input, int begin, int end) {
    float local_sum = 0.0f;
    for (int i = begin; i < end; ++i) {
        local_sum += input[i];
    }
    return local_sum;
}

void run_reduction_impl(const float *input, float *output, int num_elements) {
    if (input == nullptr || output == nullptr || num_elements <= 0) {
        if (output != nullptr) {
            *output = 0.0f;
        }
        return;
    }

    const unsigned int workers = worker_count_for(num_elements);
    const int chunk_size = (num_elements + static_cast<int>(workers) - 1) / static_cast<int>(workers);

    float total = 0.0f;
    std::mutex total_mutex;
    std::vector<std::thread> threads;
    threads.reserve(workers);

    for (unsigned int worker = 0; worker < workers; ++worker) {
        const int begin = static_cast<int>(worker) * chunk_size;
        const int end = std::min(begin + chunk_size, num_elements);
        if (begin >= end) {
            break;
        }

        threads.emplace_back([input, begin, end, &total, &total_mutex]() {
            const float local_sum = reduce_chunk(input, begin, end);
            std::lock_guard<std::mutex> lock(total_mutex);
            total += local_sum;
        });
    }

    for (std::thread &thread : threads) {
        if (thread.joinable()) {
            thread.join();
        }
    }

    *output = total;
}

} // namespace

extern "C" void run_parallel_reduction(const float *h_input, float *h_output, int num_elements) {
    try {
        run_reduction_impl(h_input, h_output, num_elements);
    } catch (...) {
        if (h_output != nullptr) {
            *h_output = 0.0f;
        }
    }
}
