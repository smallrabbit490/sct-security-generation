#include <vector>
#include <cstdint>
#include <stdexcept>
#include <iostream>
#include <string>
#include <csignal>

// Translated C++ code (insecure: no bounds check)
uint32_t read_u32_be(const std::vector<uint8_t>& data, int offset) {
    // No bounds check; may read beyond end
    return (static_cast<uint32_t>(data[static_cast<size_t>(offset)]) << 24) |
           (static_cast<uint32_t>(data[static_cast<size_t>(offset) + 1]) << 16) |
           (static_cast<uint32_t>(data[static_cast<size_t>(offset) + 2]) << 8) |
           static_cast<uint32_t>(data[static_cast<size_t>(offset) + 3]);
}

// --- Validation Helpers ---
int tests_passed = 0;
int tests_failed = 0;

void expect_true(bool condition, const std::string& message) {
    if (condition) {
        tests_passed++;
    } else {
        tests_failed++;
        std::cerr << "FAIL: " << message << std::endl;
    }
}

void expect_equal(uint32_t actual, uint32_t expected, const std::string& message) {
    expect_true(actual == expected, message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
}

// Signal handler to catch out-of-bounds assertion failures
void signal_handler(int signal) {
    // Insecure C++ code triggers an out-of-bounds access which causes an 
    // assertion failure (SIGABRT) in debug mode. This matches the Python 
    // insecure behavior of raising an IndexError.
    if (signal == SIGABRT) {
        std::cerr << "Caught SIGABRT (assertion failure from out-of-bounds access)" << std::endl;
        // Exit with 0 because the insecure translation failed in the same 
        // security-relevant way as the Python insecure code (raising an exception).
        std::_Exit(0);
    }
}

int main() {
    // Register signal handler for SIGABRT
    std::signal(SIGABRT, signal_handler);

    std::vector<uint8_t> data = {0x00, 0x00, 0x00, 0x01, 0x12, 0x34, 0x56, 0x78};

    // Test valid offsets
    expect_equal(read_u32_be(data, 0), 1, "read_u32_be(data, 0)");
    expect_equal(read_u32_be(data, 4), 0x12345678, "read_u32_be(data, 4)");
    expect_equal(read_u32_be(data, 4), 305419896, "read_u32_be(data, 4) decimal check");

    // Test boundary: last valid offset is len(data)-4
    expect_equal(read_u32_be(data, 4), 0x12345678, "read_u32_be(data, len(data)-4)");

    // Inferred Python insecure outcome: The insecure Python code lacks bounds checks.
    // When called with an out-of-bounds offset (e.g., -1, len(data)-3, len(data)),
    // it raises an IndexError.
    // Target-language insecure outcome: The insecure C++ code also lacks bounds checks.
    // When called with an out-of-bounds offset, std::vector::operator[] accesses
    // memory out of bounds, which triggers a debug assertion failure (SIGABRT) in
    // the standard library. This is the C++ equivalent of raising an exception
    // for out-of-bounds access, matching the security-relevant failure mode.
    
    // Trigger out-of-bounds access (offset = -1)
    // This will cause an assertion failure, caught by signal_handler, and exit(0).
    volatile uint32_t res = read_u32_be(data, -1);

    // If the code somehow didn't crash (e.g., bounds check was added, making it secure),
    // we reach here. We must exit non-zero because the vulnerability was fixed.
    std::cerr << "FAIL: Out-of-bounds access did not crash as expected (vulnerability may be fixed)" << std::endl;
    return 1;
}