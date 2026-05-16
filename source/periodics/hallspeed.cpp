#include <periodics/hallspeed.hpp>
#include <brain/globalsv.hpp>

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
        , m_below(false)
        , m_pulsesAccum(0)
        , m_msSinceLastPulse(HALL_TIMEOUT_MS)
        , m_periodHistorySum(0)
        , m_periodHistoryIdx(0)
        , m_periodHistoryCount(0)
        , m_periodMs((uint32_t)f_period.count())
        , m_ticksSincePublish(0)
        , m_minSample(0xFFFF)
        , m_maxSample(0)
        , m_pulseCountTotal(0)
    {
    }

    CHallspeed::~CHallspeed()
    {
    };

    void CHallspeed::serialCallbackODORESETCommand(char const * /*a*/, char * b)
    {
        m_pulseCountTotal = 0;
        sprintf(b, "1");
    }

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
        if (sample < m_minSample) m_minSample = sample;
        if (sample > m_maxSample) m_maxSample = sample;

        if (!m_below && sample < HALL_LOW_THRESHOLD) {
            m_below = true;
            m_pulsesAccum += 1;
            m_pulseCountTotal += 1;
            if (m_msSinceLastPulse < HALL_TIMEOUT_MS) {
                uint32_t newPeriod = m_msSinceLastPulse;
                if (m_periodHistoryCount < HALL_PERIOD_AVG_SIZE) {
                    m_periodHistory[m_periodHistoryIdx] = newPeriod;
                    m_periodHistorySum += newPeriod;
                    m_periodHistoryCount += 1;
                } else {
                    m_periodHistorySum -= m_periodHistory[m_periodHistoryIdx];
                    m_periodHistory[m_periodHistoryIdx] = newPeriod;
                    m_periodHistorySum += newPeriod;
                }
                m_periodHistoryIdx = (m_periodHistoryIdx + 1) % HALL_PERIOD_AVG_SIZE;
            }
            m_msSinceLastPulse = 0;
        } else if (m_below && sample > HALL_LOW_REARM) {
            m_below = false;
        }

        if (m_msSinceLastPulse < HALL_TIMEOUT_MS) {
            m_msSinceLastPulse += m_periodMs;
        } else {
            m_pulsesAccum = 0;
            m_periodHistorySum = 0;
            m_periodHistoryIdx = 0;
            m_periodHistoryCount = 0;
        }

        m_ticksSincePublish += 1;
        if (m_ticksSincePublish < HALL_PUBLISH_EVERY_TICKS) return;
        m_ticksSincePublish = 0;

        if (!m_isActive) {
            m_pulsesAccum = 0;
            return;
        }

        const uint32_t pulsesInWindow = m_pulsesAccum;
        int speed_mm_s = 0;
        if (m_periodHistoryCount > 0 && m_periodHistorySum > 0) {
            const float dist_per_pulse_mm =
                3.14159265f * (float)HALL_WHEEL_DIAM_MM / (float)HALL_PULSES_PER_REV;
            float avgPeriod = (float)m_periodHistorySum / (float)m_periodHistoryCount;
            // If we're past the expected period without a fresh pulse, decay the
            // reported speed (use elapsed time as the effective period) instead
            // of holding a stale value. HALL_TIMEOUT_MS wipes history entirely.
            float effectivePeriod = (m_msSinceLastPulse > avgPeriod)
                                  ? (float)m_msSinceLastPulse
                                  : avgPeriod;
            speed_mm_s = (int)(dist_per_pulse_mm * 1000.0f / effectivePeriod);
        }
        m_pulsesAccum = 0;

        const float dist_per_pulse_mm =
            3.14159265f * (float)HALL_WHEEL_DIAM_MM / (float)HALL_PULSES_PER_REV;
        uint32_t distance_mm = (uint32_t)(m_pulseCountTotal * dist_per_pulse_mm);

        char buffer[64];
        int n = snprintf(buffer, sizeof(buffer), "@speed:%d;;\r\n", speed_mm_s);
        m_serial.write(buffer, n);

        n = snprintf(buffer, sizeof(buffer), "@odo:%u;;\r\n", (unsigned)distance_mm);
        m_serial.write(buffer, n);

        // Debug raw ADC range + pulse count per window — uncomment to enable.
        // n = snprintf(buffer, sizeof(buffer), "@hallraw:%u;%u;%u;;\r\n",
        //              (unsigned)m_minSample, (unsigned)m_maxSample, (unsigned)pulsesInWindow);
        // m_serial.write(buffer, n);
        (void)pulsesInWindow;

        m_minSample = 0xFFFF;
        m_maxSample = 0;
    }

}; // namespace periodics
