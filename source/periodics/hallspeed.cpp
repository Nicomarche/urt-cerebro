#include <periodics/hallspeed.hpp>
#include <brain/globalsv.hpp>
#include <cmath>

#define _32_chars 32

namespace periodics
{
    CHallspeed::CHallspeed(
            std::chrono::milliseconds f_period,
            mbed::AnalogIn            f_pin,
            UnbufferedSerial&         f_serial)
        : utils::CTask(f_period)
        , m_pin(f_pin)
        , m_serial(f_serial)
        , m_isActive(true)
        , m_above(false)
        , m_pulsesAccum(0)
        , m_msSinceLastPulse(HALL_TIMEOUT_MS)
        , m_periodMs((uint32_t)f_period.count())
    {
    }

    CHallspeed::~CHallspeed()
    {
    };

    void CHallspeed::serialCallbackHALLSPEEDCommand(char const * a, char * b)
    {
        uint8_t l_isActivate = 0;
        uint8_t l_res = sscanf(a, "%hhu", &l_isActivate);

        if (1 == l_res) {
            if (uint8_globalsV_value_of_kl == 15 || uint8_globalsV_value_of_kl == 30) {
                m_isActive = (l_isActivate >= 1);
                sprintf(b, "1");
            } else {
                sprintf(b, "kl 15/30 is required!!");
            }
        } else {
            sprintf(b, "syntax error");
        }
    }

    void CHallspeed::_run()
    {
        uint16_t sample = m_pin.read_u16();

        if (!m_above && sample > HALL_THRESH_HIGH) {
            m_above = true;
            m_pulsesAccum += 1;
            m_msSinceLastPulse = 0;
        } else if (m_above && sample < HALL_THRESH_LOW) {
            m_above = false;
        }

        if (m_msSinceLastPulse < HALL_TIMEOUT_MS) {
            m_msSinceLastPulse += m_periodMs;
        } else {
            m_pulsesAccum = 0;
        }

        if (!m_isActive) return;

        int speed_mm_s = 0;
        if (m_msSinceLastPulse < HALL_TIMEOUT_MS && m_periodMs > 0) {
            const float dist_per_pulse_mm =
                (float)M_PI * (float)HALL_WHEEL_DIAM_MM / (float)HALL_PULSES_PER_REV;
            speed_mm_s = (int)((m_pulsesAccum * dist_per_pulse_mm * 1000.0f) / (float)m_periodMs);
        }
        m_pulsesAccum = 0;

        char buffer[_32_chars];
        snprintf(buffer, sizeof(buffer), "@speed:%d;;\r\n", speed_mm_s);
        m_serial.write(buffer, strlen(buffer));
    }

}; // namespace periodics
