/**
 * Hall odometer (A49E linear sensor on analog pin) — publishes longitudinal
 * speed magnitude in mm/s on the `speed` channel. Samples the ADC at the task
 * tick (1 kHz) so short magnet passes are not missed, publishes every
 * HALL_PUBLISH_EVERY_TICKS ticks.
 */

#ifndef HALLSPEED_HPP
#define HALLSPEED_HPP

#include <mbed.h>
#include <chrono>
#include <utils/task.hpp>

// Wheel calibration: tune to the real vehicle.
#define HALL_PULSES_PER_REV 1      // magnets per wheel revolution
#define HALL_WHEEL_DIAM_MM  65     // wheel diameter in mm

// Schmitt trigger on the DOWN half of the bipolar magnet pulse from the A49E.
// Idle is ~1.6V (≈33000). On each magnet pass the signal first jumps to ~2.6V
// then crosses back through baseline and dips to ~1.0V (≈19000). We only
// count the down-going crossing — the up-half is ignored to avoid counting
// the same magnet pass twice when the wheel turns slowly (the mid-pulse return
// through baseline can be longer than any reasonable rearm window).
#define HALL_LOW_THRESHOLD  28000   // ~1.41V — sample must drop below this to count
#define HALL_LOW_REARM      30000   // ~1.51V — sample must rise above this to rearm

// If no pulse arrives within this window, treat the wheel as stopped:
// wipe the period history and report 0 mm/s. Has to cover the slowest
// expected real-world rotation; at 0.1 m/s (≈10 cm/s), period ≈ 2 s.
#define HALL_TIMEOUT_MS     2500

// Publish cadence in task ticks. With task period = 1 ms this gives 50 Hz publish.
#define HALL_PUBLISH_EVERY_TICKS 20

// Number of recent inter-pulse periods to average for the published speed.
// Higher → more stable, more lag. Lower → snappier, more jitter.
#define HALL_PERIOD_AVG_SIZE 4

namespace periodics
{
    class CHallspeed : public utils::CTask
    {
        public:
            CHallspeed(
                std::chrono::milliseconds f_period,
                mbed::AnalogIn            f_pin,
                UnbufferedSerial&         f_serial
            );
            ~CHallspeed();

            void serialCallbackHALLSPEEDCommand(char const * message, char * response);
            void serialCallbackODORESETCommand(char const * message, char * response);

        private:
            virtual void _run();

            mbed::AnalogIn      m_pin;
            UnbufferedSerial&   m_serial;
            bool                m_isActive;

            bool                m_below;             // Schmitt state: true while signal is below LOW_THRESHOLD
            uint32_t            m_pulsesAccum;       // pulses counted since last publish (debug)
            uint32_t            m_msSinceLastPulse;  // for stop detection
            uint32_t            m_periodHistory[HALL_PERIOD_AVG_SIZE]; // circular buffer of recent periods
            uint32_t            m_periodHistorySum;  // running sum of m_periodHistory
            uint8_t             m_periodHistoryIdx;  // next slot to overwrite
            uint8_t             m_periodHistoryCount;// valid entries (0..HALL_PERIOD_AVG_SIZE)
            uint32_t            m_periodMs;          // task period in ms (sampling)
            uint32_t            m_ticksSincePublish; // counts up to HALL_PUBLISH_EVERY_TICKS
            uint16_t            m_minSample;         // min raw ADC in current window (debug)
            uint16_t            m_maxSample;         // max raw ADC in current window (debug)
            uint32_t            m_pulseCountTotal;   // cumulative pulses since last odoreset
    };
}

#endif // HALLSPEED_HPP
