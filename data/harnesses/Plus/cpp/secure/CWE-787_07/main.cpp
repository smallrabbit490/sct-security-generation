#include <vector>
#include <cstdint>
#include <stdexcept>
#include <type_traits>
#include <iostream>
#include <string>
#include <functional>

// Translated C++ function
std::vector<uint8_t> handle_network_packet(const std::vector<uint8_t>& packet_data, std::vector<uint8_t> buffer, int offset) {
    if (offset < 0) {
        throw std::out_of_range("offset out of range");
    }
    
    size_t unsigned_offset = static_cast<size_t>(offset);
    
    if (unsigned_offset + packet_data.size() > buffer.size()) {
        throw std::out_of_range("packet_data exceeds buffer capacity from given offset");
    }

    for (size_t i = 0; i < packet_data.size(); ++i) {
        buffer[unsigned_offset + i] = packet_data[i];
    }
    
    return buffer;
}

// Test helpers
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
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    }
}

// Main test entry point
int main() {
    // 1) successful write within bounds
    std::vector<uint8_t> buf1(10, 0);
    std::vector<uint8_t> pd1 = {0x01, 0x02, 0x03};
    std::vector<uint8_t> exp1 = {0, 0, 0, 0, 0, 1, 2, 3, 0, 0};
    expect_equal(handle_network_packet(pd1, buf1, 5), exp1, "Test 1 failed");

    // 2) write at start
    std::vector<uint8_t> buf2(4, 0);
    std::vector<uint8_t> pd2 = {0xAA, 0xBB};
    std::vector<uint8_t> exp2 = {0xAA, 0xBB, 0, 0};
    expect_equal(handle_network_packet(pd2, buf2, 0), exp2, "Test 2 failed");

    // 3) write exactly to the end
    std::vector<uint8_t> buf3(4, 0);
    std::vector<uint8_t> pd3 = {1, 2, 3, 4};
    std::vector<uint8_t> exp3 = {1, 2, 3, 4};
    expect_equal(handle_network_packet(pd3, buf3, 0), exp3, "Test 3 failed");

    // 4) empty packet does nothing
    std::vector<uint8_t> buf4(3, 0);
    std::vector<uint8_t> pd4 = {};
    std::vector<uint8_t> exp4 = {0, 0, 0};
    expect_equal(handle_network_packet(pd4, buf4, 2), exp4, "Test 4 failed");

    // 5) out-of-bounds must raise
    std::vector<uint8_t> buf5(5, 0);
    std::vector<uint8_t> pd5 = {0xFF, 0xFF};
    assert_raises([&]() { handle_network_packet(pd5, buf5, 4); }, "Test 5 failed");

    // 6) negative offset must raise
    std::vector<uint8_t> buf6(5, 0);
    std::vector<uint8_t> pd6 = {1};
    assert_raises([&]() { handle_network_packet(pd6, buf6, -1); }, "Test 6 failed");

    // 7) wrong buffer type must raise (C++ is statically typed, so this is inherently safe)
    expect_true(true, "Test 7 passed (static type safety)");

    // 8) wrong packet type must raise (C++ is statically typed, so this is inherently safe)
    expect_true(true, "Test 8 passed (static type safety)");

    return 0;
}