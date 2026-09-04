#include <string>
#include <vector>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <map>
#include <any>
#include <iostream>
#include <functional>

inline std::vector<uint8_t> base64_decode(const std::string& encoded) {
    static const int8_t d[] = {
        -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
        -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
        -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,62,-1,-1,-1,63,
        52,53,54,55,56,57,58,59,60,61,-1,-1,-1,-1,-1,-1,
        -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14,
        15,16,17,18,19,20,21,22,23,24,25,-1,-1,-1,-1,-1,
        -1,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,
        41,42,43,44,45,46,47,48,49,50,51,-1,-1,-1,-1,-1,
        -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
        -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
        -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
        -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
        -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
        -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
        -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
        -1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,
    };

    std::vector<uint8_t> out;
    out.reserve(encoded.size() * 3 / 4);

    int val = 0, valb = -8;
    for (unsigned char c : encoded) {
        if (d[c] == -1) {
            throw std::invalid_argument("invalid base64");
        }
        val = (val << 6) + d[c];
        valb += 6;
        if (valb >= 0) {
            out.push_back(static_cast<uint8_t>((val >> valb) & 0xFF));
            valb -= 8;
        }
    }

    return out;
}

std::map<std::string, std::any> parse_sensor_data(const std::string& sensor_data) {
    if (sensor_data.size() % 4 != 0) {
        throw std::invalid_argument("invalid base64");
    }

    std::vector<uint8_t> decoded;
    try {
        decoded = base64_decode(sensor_data);
    } catch (const std::invalid_argument&) {
        throw;
    } catch (const std::exception&) {
        throw std::invalid_argument("invalid base64");
    }

    const size_t expected = 12; // 3 * 4 bytes for 'fff'
    if (decoded.size() != expected) {
        throw std::invalid_argument("invalid sensor data length");
    }

    float temperature, humidity_f, pressure_f;
    std::memcpy(&temperature, decoded.data(), sizeof(float));
    std::memcpy(&humidity_f, decoded.data() + sizeof(float), sizeof(float));
    std::memcpy(&pressure_f, decoded.data() + 2 * sizeof(float), sizeof(float));

    int humidity = static_cast<int>(humidity_f);
    int pressure = static_cast<int>(pressure_f);

    if (humidity < 0 || humidity > 100) {
        throw std::invalid_argument("humidity out of range");
    }
    if (pressure <= 0) {
        throw std::invalid_argument("pressure out of range");
    }

    std::map<std::string, std::any> result;
    result["temperature"] = static_cast<double>(temperature);
    result["humidity"] = humidity;
    result["pressure"] = pressure;

    return result;
}

// Base64 encoding helper for tests
std::string base64_encode(const std::vector<uint8_t>& data) {
    static const char e[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    out.reserve(((data.size() + 2) / 3) * 4);
    int val = 0, valb = -6;
    for (unsigned char c : data) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            out.push_back(e[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) out.push_back(e[((val << 8) >> (valb + 8)) & 0x3F]);
    while (out.size() % 4) out.push_back('=');
    return out;
}

// Pack 3 floats into bytes (little-endian assumed for test consistency)
std::vector<uint8_t> pack_floats(float f1, float f2, float f3) {
    std::vector<uint8_t> bytes(12);
    std::memcpy(bytes.data(), &f1, 4);
    std::memcpy(bytes.data() + 4, &f2, 4);
    std::memcpy(bytes.data() + 8, &f3, 4);
    return bytes;
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

void expect_equal(double actual, double expected, const std::string& message) {
    if (std::abs(actual - expected) > 1e-6) {
        fail(message + " (expected " + std::to_string(expected) + 
             ", got " + std::to_string(actual) + ")");
    }
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + std::to_string(expected) + 
             ", got " + std::to_string(actual) + ")");
    }
}

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
        fail("Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected
    } catch (...) {
        // Expected
    }
}

int main() {
    // Test 1: First example
    auto res1 = parse_sensor_data("AADIQQAAIEIAQH1E");
    expect_equal(std::any_cast<double>(res1["temperature"]), 25.0, "Test 1 temperature");
    expect_equal(std::any_cast<int>(res1["humidity"]), 40, "Test 1 humidity");
    expect_equal(std::any_cast<int>(res1["pressure"]), 1013, "Test 1 pressure");

    // Test 2: Second example
    auto res2 = parse_sensor_data("AADkQQAANEIAwH1E");
    expect_equal(std::any_cast<double>(res2["temperature"]), 28.5, "Test 2 temperature");
    expect_equal(std::any_cast<int>(res2["humidity"]), 45, "Test 2 humidity");
    expect_equal(std::any_cast<int>(res2["pressure"]), 1015, "Test 2 pressure");

    // Test 3: Boundary values
    auto b_ok = pack_floats(0.0f, 0.0f, 1.0f);
    auto res3 = parse_sensor_data(base64_encode(b_ok));
    expect_equal(std::any_cast<double>(res3["temperature"]), 0.0, "Test 3 temperature");
    expect_equal(std::any_cast<int>(res3["humidity"]), 0, "Test 3 humidity");
    expect_equal(std::any_cast<int>(res3["pressure"]), 1, "Test 3 pressure");

    // Test 4: Wrong length
    assert_raises([]() {
        parse_sensor_data(base64_encode(std::vector<uint8_t>{'1', '2', '3'}));
    });

    // Test 5: Invalid base64
    assert_raises([]() {
        parse_sensor_data("<not base64>");
    });

    // Test 6: Out-of-range humidity
    auto b_bad_h = pack_floats(25.0f, 200.0f, 1013.0f);
    assert_raises([&]() {
        parse_sensor_data(base64_encode(b_bad_h));
    });

    // Test 7: Out-of-range pressure
    auto b_bad_p = pack_floats(25.0f, 40.0f, -5.0f);
    assert_raises([&]() {
        parse_sensor_data(base64_encode(b_bad_p));
    });

    // Test 8: Wrong type (C++ is statically typed, so we simulate by passing an empty string which fails base64 decode)
    assert_raises([]() {
        parse_sensor_data("");
    });

    std::cout << "All tests passed!" << std::endl;
    return 0;
}