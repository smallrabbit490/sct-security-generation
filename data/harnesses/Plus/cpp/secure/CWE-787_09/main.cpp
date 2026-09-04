#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>
#include <iostream>
#include <functional>

std::vector<uint8_t> copy_into_fixed_buffer(const std::vector<uint8_t>& src, int capacity) {
    if (capacity < 0) {
        throw std::invalid_argument("capacity must be non-negative");
    }

    if (static_cast<std::ptrdiff_t>(src.size()) > capacity) {
        throw std::invalid_argument("source exceeds buffer capacity");
    }

    std::vector<uint8_t> buf(static_cast<std::size_t>(capacity), 0);
    for (std::size_t i = 0; i < src.size(); ++i) {
        buf[i] = src[i];
    }
    
    return buf;
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

void expect_equal(const std::vector<uint8_t>& actual, const std::vector<uint8_t>& expected, const std::string& message) {
    if (actual != expected) {
        std::string actual_str;
        for (auto byte : actual) { actual_str += std::to_string(static_cast<int>(byte)) + " "; }
        std::string expected_str;
        for (auto byte : expected) { expected_str += std::to_string(static_cast<int>(byte)) + " "; }
        fail(message + " - Expected [" + expected_str + "], got [" + actual_str + "]");
    }
}

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::exception&) {
        return; // Exception caught as expected
    }
    fail("Expected an exception but none was raised");
}

int main() {
    // normal copy, remaining bytes stay as 0x00
    expect_equal(
        copy_into_fixed_buffer({0x41, 0x42, 0x43}, 5),
        {0x41, 0x42, 0x43, 0x00, 0x00},
        "candidate(b\"ABC\", 5) == b\"ABC\\x00\\x00\""
    );

    expect_equal(
        copy_into_fixed_buffer({}, 3),
        {0x00, 0x00, 0x00},
        "candidate(b\"\", 3) == b\"\\x00\\x00\\x00\""
    );

    expect_equal(
        copy_into_fixed_buffer({0xFF, 0x00}, 2),
        {0xFF, 0x00},
        "candidate(b\"\\xff\\x00\", 2) == b\"\\xff\\x00\""
    );

    // overflow should raise
    assert_raises([]() {
        copy_into_fixed_buffer({0x54, 0x4F, 0x4F, 0x2D, 0x4C, 0x4F, 0x4E, 0x47}, 3); // "TOO-LONG"
    });

    // invalid args
    assert_raises([]() {
        copy_into_fixed_buffer({0x41, 0x42, 0x43}, -1);
    });

    // C++ type safety naturally prevents passing strings where vectors are expected,
    // making the TypeError checks for "ABC" and "5" inapplicable in this strongly typed translation.

    return 0;
}