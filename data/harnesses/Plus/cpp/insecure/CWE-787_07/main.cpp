#include <vector>
#include <cstdint>
#include <stdexcept>
#include <iostream>
#include <string>

using Buffer = std::vector<uint8_t>;

// Translated C++ code (insecure version)
Buffer handle_network_packet(const std::vector<uint8_t>& packet_data, Buffer buffer, int offset) {
    for (size_t i = 0; i < packet_data.size(); ++i) {
        size_t index = static_cast<size_t>(offset) + i;
        if (index >= buffer.size()) {
            throw std::out_of_range("Buffer index out of bounds");
        }
        buffer[index] = packet_data[i];
    }
    return buffer;
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
        fail(message);
    }
}

// Inferred Python insecure outcome:
// For out-of-bounds offset (e.g., offset=4, buffer size=5, packet size=2), the insecure Python code
// raises an IndexError mid-loop when it attempts to write past the buffer's end.
// For negative offset (e.g., offset=-1), the insecure Python code raises an IndexError because
// negative indexing on bytearray is not permitted for assignment in this context.
//
// Target-language outcome being compared:
// The translated C++ code throws std::out_of_range for out-of-bounds and negative offsets.
// This matches the insecure Python behavior (raising an exception).
// If the translation were "secure" (e.g., silently resizing the buffer or wrapping around),
// it would not raise an exception, and the validation must fail (exit non-zero).
// If the translation crashes due to an unhandled assertion (like std::vector's debug bounds check),
// it is an uncontrolled failure, not a proper exception, so the validation must fail (exit non-zero).

int main() {
    // 1) successful write within bounds
    Buffer buf1(10, 0);
    Buffer expected1 = {0, 0, 0, 0, 0, 1, 2, 3, 0, 0};
    Buffer result1 = handle_network_packet({0x01, 0x02, 0x03}, buf1, 5);
    expect_equal(result1, expected1, "Test 1 failed: successful write within bounds");

    // 2) write at start
    Buffer buf2(4, 0);
    Buffer expected2 = {0xAA, 0xBB, 0, 0};
    Buffer result2 = handle_network_packet({0xAA, 0xBB}, buf2, 0);
    expect_equal(result2, expected2, "Test 2 failed: write at start");

    // 3) write exactly to the end
    Buffer buf3(4, 0);
    Buffer expected3 = {1, 2, 3, 4};
    Buffer result3 = handle_network_packet({1, 2, 3, 4}, buf3, 0);
    expect_equal(result3, expected3, "Test 3 failed: write exactly to the end");

    // 4) empty packet does nothing
    Buffer buf4(3, 0);
    Buffer expected4 = {0, 0, 0};
    Buffer result4 = handle_network_packet({}, buf4, 2);
    expect_equal(result4, expected4, "Test 4 failed: empty packet does nothing");

    // 5) out-of-bounds must raise (insecure raises IndexError mid-loop, C++ must throw std::out_of_range)
    Buffer buf5(5, 0);
    bool raised5 = false;
    try {
        handle_network_packet({0xFF, 0xFF}, buf5, 4);
    } catch (const std::out_of_range&) {
        raised5 = true;
    } catch (...) {
        fail("Test 5 failed: unexpected exception type for out-of-bounds offset");
    }
    expect_true(raised5, "Test 5 failed: expected std::out_of_range for out-of-bounds offset but none was raised");

    // 6) negative offset must raise (insecure raises IndexError, C++ must throw std::out_of_range)
    Buffer buf6(5, 0);
    bool raised6 = false;
    try {
        handle_network_packet({1}, buf6, -1);
    } catch (const std::out_of_range&) {
        raised6 = true;
    } catch (...) {
        fail("Test 6 failed: unexpected exception type for negative offset");
    }
    expect_true(raised6, "Test 6 failed: expected std::out_of_range for negative offset but none was raised");

    // 7) wrong buffer type must raise (C++ type system enforces this at compile time, no runtime check needed)
    // 8) wrong packet type must raise (C++ type system enforces this at compile time, no runtime check needed)

    std::cout << "All tests passed" << std::endl;
    return 0;
}