/**
 * Hall odometer (A49E linear sensor on analog pin) — publishes longitudinal
 * speed magnitude in mm/s on the `speed` channel at the task period.
 */

#ifndef HALLSPEED_HPP
#define HALLSPEED_HPP

#include <mbed.h>
#include <chrono>
#include <utils/task.hpp>

// Wheel calibration: tune to the real vehicle.
#define HALL_PULSES_PER_REV 1      // magnets per wheel revolution
#define HALL_WHEEL_DIAM_MM  65     // wheel diameter in mm

// Schmitt-style thresholds for read_u16 (0..65535) coming from the A49E.
// Measured on this unit: ~1.6V idle (≈31774) and ~2.6V with magnet (≈51632) at VREF=3.3V.
// Thresholds sit at ~2.3V high / ~1.9V low to give margin on both sides plus hysteresis.
#define HALL_THRESH_HIGH    46000
#define HALL_THRESH_LOW     38000

// If no pulse arrives within this window, force published speed to 0.
#define HALL_TIMEOUT_MS     300

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

        private:
            virtual void _run();

            mbed::AnalogIn      m_pin;
            UnbufferedSerial&   m_serial;
            bool                m_isActive;

            bool                m_above;             // software Schmitt state
            uint32_t            m_pulsesAccum;       // pulses counted since last publish
            uint32_t            m_msSinceLastPulse;  // for stop detection
            uint32_t            m_periodMs;          // task period in ms
    };
}

#endif // HALLSPEED_HPP
