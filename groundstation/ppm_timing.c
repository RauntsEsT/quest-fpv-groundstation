/*
 * ppm_timing.c — PPM ajastus + RP1 otsene GPIO mmap (RPi5)
 * v2: ARM CNTVCT_EL0 (54 MHz, ~18 ns täpsus, null syscall)
 *
 * Kompileeri: gcc -O2 -shared -fPIC -o ppm_timing.so ppm_timing.c -lm
 */
#include <time.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <math.h>

/* ── ARM generic timer ───────────────────────────────────────────────────
 * cntvct_el0: loeb fikseeritud sagedusega taimerit (RPi5: 54 MHz).
 * Üks mrs-instruktsioon ≈ 2 ns vs clock_gettime vDSO ≈ 50-200 ns.
 * ─────────────────────────────────────────────────────────────────────── */
static uint64_t g_ticks_per_us = 54;

static inline uint64_t read_cntvct(void) {
    uint64_t v;
    __asm__ __volatile__("mrs %0, cntvct_el0" : "=r"(v));
    return v;
}

static void init_arm_timer(void) {
    uint64_t freq;
    __asm__ __volatile__("mrs %0, cntfrq_el0" : "=r"(freq));
    if (freq > 1000000ULL && freq < 500000000ULL)
        g_ticks_per_us = freq / 1000000ULL;
}

static inline uint64_t us2t(int us) {
    return (uint64_t)(unsigned int)us * g_ticks_per_us;
}

static inline void wait_until(uint64_t target) {
    while (read_cntvct() < target);
}

/* ── Tagasilangus: clock_gettime (kasutatakse ainult lgpio fallback-is) ── */
static inline long now_ns_impl(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (long)ts.tv_sec * 1000000000L + (long)ts.tv_nsec;
}
void busywait_us(long us) {
    long end = now_ns_impl() + us * 1000L;
    while (now_ns_impl() < end) {}
}
void busywait_until_ns(long target_ns) {
    while (now_ns_impl() < target_ns) {}
}
long monotonic_ns(void) { return now_ns_impl(); }

/* ── RP1 GPIO mmap ───────────────────────────────────────────────────── */
#define RP1_GPIO_PHYS   ((off_t)0x1f000d0000LL)
#define RP1_MMAP_SIZE   0x14000u
#define RIO_SET_OFFSET  0x12000u
#define RIO_CLR_OFFSET  0x13000u

static volatile uint32_t *g_rio_set   = NULL;
static volatile uint32_t *g_rio_clr   = NULL;
static uint32_t            g_gpio_mask = 0;
static void               *g_mmap_base = NULL;

int rp1_gpio_mmap_init(int gpio_pin) {
    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) return -1;
    void *base = mmap(NULL, RP1_MMAP_SIZE, PROT_READ | PROT_WRITE,
                      MAP_SHARED, fd, RP1_GPIO_PHYS);
    close(fd);
    if (base == MAP_FAILED) return -1;
    g_mmap_base = base;
    g_gpio_mask = (uint32_t)(1u << gpio_pin);
    g_rio_set   = (volatile uint32_t *)((uint8_t *)base + RIO_SET_OFFSET);
    g_rio_clr   = (volatile uint32_t *)((uint8_t *)base + RIO_CLR_OFFSET);
    init_arm_timer();
    return 0;
}

void rp1_gpio_mmap_close(void) {
    if (g_mmap_base) {
        munmap(g_mmap_base, RP1_MMAP_SIZE);
        g_mmap_base = NULL; g_rio_set = NULL; g_rio_clr = NULL;
    }
}

/* ── PPM loop ─────────────────────────────────────────────────────────── *
 * Kõik ajastused ARM cntvct_el0 kaudu — null syscall overhead.           *
 * ─────────────────────────────────────────────────────────────────────── */
long rp1_ppm_run(
    volatile int   *running,
    volatile int   *ch_us,
    int             num_ch,
    int             frame_us,
    int             pulse_us,
    volatile double *jitter_out
) {
    if (!g_rio_set || !g_rio_clr) return -1L;

    long   frames  = 0;
    double sum_err = 0.0, sum_sq = 0.0, max_err = 0.0;

    uint64_t pulse_ticks = us2t(pulse_us);

    while (*running) {
        int chs[16];
        int n = (num_ch < 16) ? num_ch : 16;
        for (int i = 0; i < n; i++) chs[i] = ch_us[i];

        int total_ch = 0;
        for (int i = 0; i < n; i++) total_ch += chs[i];
        int sync_gap = frame_us - total_ch - pulse_us;
        if (sync_gap < 3000) sync_gap = 3000;

        /* Raami algus — võetakse kohe, iga raam algab kaasajast */
        uint64_t t = read_cntvct();

        for (int i = 0; i < n; i++) {
            *g_rio_set = g_gpio_mask;            /* marker pulss KÕRGE */
            t += pulse_ticks;
            wait_until(t);
            *g_rio_clr = g_gpio_mask;            /* marker pulss MADAL */
            t += us2t(chs[i] - pulse_us);        /* kanalitühik */
            wait_until(t);
        }

        /* Sünkroonimisvahepulss */
        *g_rio_set = g_gpio_mask;
        t += pulse_ticks;
        wait_until(t);
        *g_rio_clr = g_gpio_mask;
        t += us2t(sync_gap);
        wait_until(t);

        /* Jitter = kui palju me sihtajast mööda läksime */
        uint64_t actual = read_cntvct();
        double err = (double)(int64_t)(actual - t) / (double)g_ticks_per_us;
        if (err < 0.0) err = 0.0;
        if (err > max_err) max_err = err;
        sum_err += err;
        sum_sq  += err * err;
        frames++;

        if (jitter_out && (frames & 0xFF) == 0) {
            double avg = sum_err / (double)frames;
            double var = sum_sq  / (double)frames - avg * avg;
            jitter_out[0] = avg;
            jitter_out[1] = max_err;
            jitter_out[2] = (var > 0.0) ? sqrt(var) : 0.0;
            jitter_out[3] = (double)frames;
        }
    }

    if (g_rio_clr) *g_rio_clr = g_gpio_mask;
    return frames;
}
