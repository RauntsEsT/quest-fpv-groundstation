/*
 * ppm_timing.c - PPM ajastus C-s (ainult wait), GPIO jaab Pythoni
 * gcc -O2 -shared -fPIC -o ppm_timing.so ppm_timing.c
 */
#include <time.h>

static long now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (long)ts.tv_sec * 1000000000L + (long)ts.tv_nsec;
}

/* Busywait us mikrosekundi (tahajaanud kasutus) */
void busywait_us(long us) {
    long end = now_ns() + us * 1000L;
    while (now_ns() < end) {}
}

/* Busywait kuni absoluutse ns ajatemponi.
 * Kompenseerib gpio_write() lahtence — iga transition sihtib absoluutset aega,
 * mitte relatiivset viivitust. Valtib kumulatiivset triivi PPM frameis. */
void busywait_until_ns(long target_ns) {
    while (now_ns() < target_ns) {}
}

/* Tagastab praeguse aja nanosekuntides */
long monotonic_ns(void) {
    return now_ns();
}
