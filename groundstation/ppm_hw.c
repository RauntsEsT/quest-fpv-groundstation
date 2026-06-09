/*
 * ppm_hw.c — hardware-timed PPM generator for RPi5 (RP1 GPIO via lgpio)
 *
 * Kompileeri: gcc -O2 -shared -fPIC -o ppm_hw.so ppm_hw.c -lgpiod
 * Kasutus: laetakse Python ctypes kaudu — vabastab GIL kogu PPM loopi jooksul
 *
 * Ajastus: CLOCK_MONOTONIC_RAW busy-wait (ei ole mõjutatud NTP/adjtime).
 * Prioriteet: helistaja peab seadma SCHED_FIFO enne selle funktsiooni kutsumist.
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <time.h>
#include <sched.h>

/* Ajastuse abifunktsioon — busy-wait mikrosekundi täpsusega */
static inline void wait_us(long us) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    long end_ns = (long)ts.tv_sec * 1000000000L + ts.tv_nsec + us * 1000L;
    do {
        clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    } while ((long)ts.tv_sec * 1000000000L + ts.tv_nsec < end_ns);
}

/*
 * ppm_loop — peamine PPM genereerimise tsükkel
 *
 * Parameetrid:
 *   chip_fd   — lgpio gpiochip handle (int)
 *   gpio_pin  — GPIO number (nt 18)
 *   channels  — 8 int-i vahemikus 1000-2000 (mikrosekund)
 *   n_ch      — kanalite arv (maks 8)
 *   pulse_us  — pulsi laius (300µs)
 *   frame_us  — kaadriaeg (22500µs = 22.5ms)
 *   running   — pointer int-ile; 0 = lõpeta
 *
 * MÄRKUS: see funktsioon blokeerib kuni *running == 0.
 * Python kutsub seda run_in_executor kaudu — GIL on vabastatud.
 */

/* lgpio gpio_write funktsioon — linkime dünaamiliselt Python-ist */
typedef int (*lgpio_write_fn)(int handle, int gpio, int level);

void ppm_loop_c(int chip_fd, int gpio_pin,
                volatile int *channels, int n_ch,
                int pulse_us, int frame_us,
                volatile int *running,
                lgpio_write_fn gpio_write) {

    /* Pin isoleeritud CPU tuumale */
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(3, &cpuset);
    sched_setaffinity(0, sizeof(cpuset), &cpuset);

    while (*running) {
        int used = 0;

        /* 8 kanalit: HIGH(pulse_us) + LOW(ch_us - pulse_us) */
        for (int i = 0; i < n_ch; i++) {
            int ch_us = channels[i];
            if (ch_us < 1000) ch_us = 1000;
            if (ch_us > 2000) ch_us = 2000;

            gpio_write(chip_fd, gpio_pin, 1);
            wait_us(pulse_us);
            gpio_write(chip_fd, gpio_pin, 0);
            wait_us(ch_us - pulse_us);

            used += ch_us;
        }

        /* Sync pulse + gap */
        int sync_gap = frame_us - used - n_ch * pulse_us - pulse_us;
        if (sync_gap < 3000) sync_gap = 3000;

        gpio_write(chip_fd, gpio_pin, 1);
        wait_us(pulse_us);
        gpio_write(chip_fd, gpio_pin, 0);
        wait_us(sync_gap);
    }

    gpio_write(chip_fd, gpio_pin, 0);
}
