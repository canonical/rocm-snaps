#include <hip/hip_runtime.h>
#include <hiprand/hiprand.h>
#include <rocblas/rocblas.h>

#include <cmath>
#include <cstdio>

int main() {
    float *device_x = nullptr;
    float *device_y = nullptr;
    rocblas_handle blas = nullptr;
    hiprandGenerator_t rand = nullptr;
    const float alpha = 2.0f;
    float result = 0.0f;

    if (hipMalloc(&device_x, sizeof(float)) != hipSuccess ||
        hipMalloc(&device_y, sizeof(float)) != hipSuccess ||
        rocblas_create_handle(&blas) != rocblas_status_success ||
        hiprandCreateGenerator(&rand, HIPRAND_RNG_PSEUDO_DEFAULT) != HIPRAND_STATUS_SUCCESS ||
        hiprandSetPseudoRandomGeneratorSeed(rand, 1) != HIPRAND_STATUS_SUCCESS ||
        hiprandGenerateUniform(rand, device_x, 1) != HIPRAND_STATUS_SUCCESS ||
        hipMemset(device_y, 0, sizeof(float)) != hipSuccess ||
        rocblas_saxpy(blas, 1, &alpha, device_x, 1, device_y, 1) != rocblas_status_success ||
        hipDeviceSynchronize() != hipSuccess ||
        hipMemcpy(&result, device_y, sizeof(float), hipMemcpyDeviceToHost) != hipSuccess ||
        !std::isfinite(result) || result < 0.0f || result > 2.0f) {
        std::fputs("HIP/rocBLAS/hipRAND smoke test failed\n", stderr);
        return 1;
    }

    hiprandDestroyGenerator(rand);
    rocblas_destroy_handle(blas);
    if (hipFree(device_y) != hipSuccess || hipFree(device_x) != hipSuccess) {
        std::fputs("HIP cleanup failed\n", stderr);
        return 1;
    }
    std::printf("HIP/rocBLAS/hipRAND: %f\n", result);
    return 0;
}
