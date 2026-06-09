/*
 * ppm_timing.c - PPM ajastus C-s (ainult wait), GPIO jääb Pythoni
 * gcc -O2 -shared -fPIC -o ppm_timing.so ppm_timing.c
 */
#include <time.h>

static long now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (long)ts.tv_sec * 1000000000L + (long)ts.tv_nsec;
}

/* Busywait us mikrosekundi — vabastab Python GIL (ctypes kutsutud) */
void busywait_us(long us) {
    long end = now_ns() + us * 1000L;
    while (now_ns() < end) {}
}

/* Tagastab praeguse aja nanosekuntides */
long monotonic_ns(void) {
    return now_ns();
}
