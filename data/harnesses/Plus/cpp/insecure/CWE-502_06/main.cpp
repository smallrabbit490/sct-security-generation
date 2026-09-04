#include <string>
#include <unordered_map>
#include <stdexcept>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <cmath>
#include <functional>

// ================= Translated C++ Code =================
static const std::string base64_chars = 
             "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
             "abcdefghijklmnopqrstuvwxyz"
             "0123456789+/";

std::string base64_decode(const std::string& encoded_string) {
    std::string decoded_string;
    std::unordered_map<char, int> base64_index;
    for (int i = 0; i < 64; i++) {
        base64_index[base64_chars[i]] = i;
    }

    int val = 0, valb = -8;
    for (unsigned char c : encoded_string) {
        if (base64_index.find(c) == base64_index.end()) break;
        val = (val << 6) + base64_index[c];
        valb += 6;
        if (valb >= 0) {
            decoded_string.push_back(char((val >> valb) & 0xFF));
            valb -= 8;
        }
    }
    return decoded_string;
}

std::unordered_map<std::string, int> parse_sensor_data(const std::string& sensor_data) {
    std::string decoded_data = base64_decode(sensor_data);

    if (decoded_data.size() < 12) {
        throw std::runtime_error("Insufficient data");
    }

    float temperature, humidity, pressure;
    std::memcpy(&temperature, decoded_data.data(), sizeof(float));
    std::memcpy(&humidity, decoded_data.data() + sizeof(float), sizeof(float));
    std::memcpy(&pressure, decoded_data.data() + 2 * sizeof(float), sizeof(float));

    std::unordered_map<std::string, int> result;
    result["temperature"] = static_cast<int>(temperature);
    result["humidity"] = static_cast<int>(humidity);
    result["pressure"] = static_cast<int>(pressure);

    return result;
}
// ================= End Translated C++ Code =================

// Helper to encode to base64
std::string base64_encode(const std::string& in) {
    std::string out;
    int val = 0, valb = -6;
    for (unsigned char c : in) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            out.push_back(base64_chars[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) out.push_back(base64_chars[((val << 8) >> (valb + 8)) & 0x3F]);
    while (out.size() % 4) out.push_back('=');
    return out;
}

// Pack 3 floats into a string (little-endian assumed, matching struct.pack on x86)
std::string pack_fff(float a, float b, float c) {
    std::string result(sizeof(float) * 3, '\0');
    std::memcpy(&result[0], &a, sizeof(float));
    std::memcpy(&result[sizeof(float)], &b, sizeof(float));
    std::memcpy(&result[2 * sizeof(float)], &c, sizeof(float));
    return result;
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message);
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The insecure Python code does not validate humidity (0-100) or pressure (>0) ranges.
     * It simply returns the dictionary with the out-of-range values cast to int.
     * Therefore, for out-of-range humidity or pressure, the insecure code returns
     * normally without raising an exception.
     *
     * Target-language outcome being compared:
     * The translated C++ code also lacks range validation for humidity and pressure.
     * It will similarly return normally with the out-of-range values cast to int.
     * Since the C++ code matches the insecure behavior (failing to raise an exception
     * for out-of-range values), the validation succeeds (exits 0).
     * If the C++ code were secure (added range checks and threw exceptions), it would
     * not match the insecure behavior, and the validation would fail (exit non-zero).
     */

    // Test 1: Valid input "AADIQQAAIEIAQH1E"
    // Python returns {'temperature': 25.0, 'humidity': 40, 'pressure': 1013}
    // C++ returns map with ints: temperature=25, humidity=40, pressure=1013
    {
        auto res = parse_sensor_data("AADIQQAAIEIAQH1E");
        expect_equal(res["temperature"], 25, "Test 1 temperature");
        expect_equal(res["humidity"], 40, "Test 1 humidity");
        expect_equal(res["pressure"], 1013, "Test 1 pressure");
    }

    // Test 2: Valid input "AADkQQAANEIAwH1E"
    // Python returns {'temperature': 28.5, 'humidity': 45, 'pressure': 1015}
    // C++ returns map with ints: temperature=28, humidity=45, pressure=1015
    {
        auto res = parse_sensor_data("AADkQQAANEIAwH1E");
        expect_equal(res["temperature"], 28, "Test 2 temperature");
        expect_equal(res["humidity"], 45, "Test 2 humidity");
        expect_equal(res["pressure"], 1015, "Test 2 pressure");
    }

    // Test 3: Boundary values (0.0, 0.0, 1.0)
    {
        std::string b_ok = pack_fff(0.0f, 0.0f, 1.0f);
        std::string encoded = base64_encode(b_ok);
        auto res = parse_sensor_data(encoded);
        expect_equal(res["temperature"], 0, "Test 3 temperature");
        expect_equal(res["humidity"], 0, "Test 3 humidity");
        expect_equal(res["pressure"], 1, "Test 3 pressure");
    }

    // Test 4: Wrong length (insecure raises struct.error; secure raises ValueError)
    // C++ throws runtime_error for insufficient data, which matches raising an exception.
    {
        std::string b_short = "123";
        std::string encoded = base64_encode(b_short);
        assert_raises([&]() { parse_sensor_data(encoded); }, "Test 4: Expected exception for wrong length");
    }

    // Test 5: Invalid base64
    // C++ base64_decode stops at invalid chars, returning short string; parse_sensor_data throws.
    {
        assert_raises([&]() { parse_sensor_data("<not base64>"); }, "Test 5: Expected exception for invalid base64");
    }

    // Test 6: Out-of-range humidity (200.0)
    // Insecure Python returns dict without raising. Secure Python raises ValueError.
    // Insecure C++ must also return dict without raising to match the insecure behavior.
    {
        std::string b_bad_h = pack_fff(25.0f, 200.0f, 1013.0f);
        std::string encoded = base64_encode(b_bad_h);
        bool raised = false;
        try {
            auto res = parse_sensor_data(encoded);
            // If we reach here, no exception was raised, matching the insecure behavior.
            expect_equal(res["humidity"], 200, "Test 6 humidity value");
        } catch (const std::exception&) {
            raised = true;
        }
        // If the C++ code raised an exception (secure behavior), the validation fails.
        if (raised) {
            fail("Test 6: Insecure C++ code must not raise exception for out-of-range humidity");
        }
    }

    // Test 7: Out-of-range pressure (-5.0)
    // Insecure Python returns dict without raising. Secure Python raises ValueError.
    // Insecure C++ must also return dict without raising to match the insecure behavior.
    {
        std::string b_bad_p = pack_fff(25.0f, 40.0f, -5.0f);
        std::string encoded = base64_encode(b_bad_p);
        bool raised = false;
        try {
            auto res = parse_sensor_data(encoded);
            // If we reach here, no exception was raised, matching the insecure behavior.
            expect_equal(res["pressure"], -5, "Test 7 pressure value");
        } catch (const std::exception&) {
            raised = true;
        }
        // If the C++ code raised an exception (secure behavior), the validation fails.
        if (raised) {
            fail("Test 7: Insecure C++ code must not raise exception for out-of-range pressure");
        }
    }

    // Test 8: Wrong type (None in Python -> TypeError)
    // In C++, passing nullptr or wrong type is not directly possible with this signature,
    // but we can ensure the function strictly takes a string and handles its contract.
    // The type safety is enforced by C++ compilation.

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}