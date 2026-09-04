#include <vector>
#include <cstdint>
#include <stdexcept>
#include <iostream>
#include <string>
#include <functional>

uint32_t read_u32_be(const std::vector<uint8_t>& data, int offset) {
    if (offset < 0 || static_cast<size_t>(offset) + 4 > data.size()) {
        throw std::out_of_range("read out of bounds");
    }

    uint32_t b0 = data[offset];
    uint32_t b1 = data[offset + 1];
    uint32_t b2 = data[offset + 2];
    uint32_t b3 = data[offset + 3];

    return (b0 << 24) | (b1 << 16) | (b2 << 8) | b3;
}

int tests_failed = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    tests_failed++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

template <typename T>
void expect_equal(T actual, T expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
        fail("Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        fail("Raised an unexpected non-exception type");
    }
}

int main() {
    std::vector<uint8_t> data = {0x00, 0x00, 0x00, 0x01, 0x12, 0x34, 0x56, 0x78};

    // Basic reads
    expect_equal(read_u32_be(data, 0), static_cast<uint32_t>(1), "read_u32_be(data, 0) should be 1");
    expect_equal(read_u32_be(data, 4), static_cast<uint32_t>(0x12345678), "read_u32_be(data, 4) should be 0x12345678");

    // boundary: last valid offset is len(data)-4
    expect_equal(read_u32_be(data, static_cast<int>(data.size()) - 4), static_cast<uint32_t>(0x12345678), "read_u32_be(data, len(data) - 4) should be 0x12345678");

    // out of bounds
    assert_raises([&]() { read_u32_be(data, -1); });
    assert_raises([&]() { read_u32_be(data, static_cast<int>(data.size()) - 3); });
    assert_raises([&]() { read_u32_be(data, static_cast<int>(data.size())); });

    // wrong types (C++ is statically typed, so passing a string or incorrect type is a compile-time error.
    // We simulate the Python test's intent by ensuring our function signature strictly enforces types,
    // and that invalid bounds are caught at runtime).

    if (tests_failed > 0) {
        std::cerr << tests_failed << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}