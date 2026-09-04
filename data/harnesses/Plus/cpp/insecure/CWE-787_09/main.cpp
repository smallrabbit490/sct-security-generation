#include <vector>
#include <cstdint>
#include <iostream>
#include <string>
#include <stdexcept>

// Translated C++ code (insecure version)
std::vector<uint8_t> copy_into_fixed_buffer(const std::vector<uint8_t>& src, int capacity) {
    std::vector<uint8_t> buf(capacity, 0);
    // Unsafe: may write past the end when src is larger than capacity
    for (size_t i = 0; i < src.size(); i++) {
        buf[i] = src[i];
    }
    return buf;
}

// Helper to signal test failure and exit with non-zero code
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

// Helper to check boolean conditions
void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

// Helper to check if calling a function throws a specific exception type
template <typename ExceptionType, typename Func, typename... Args>
void expect_throws(Func func, Args&&... args, const std::string& message) {
    try {
        func(std::forward<Args>(args)...);
        fail(message + " - Expected an exception but none was raised");
    } catch (const ExceptionType&) {
        // Correctly threw the expected exception type
    } catch (...) {
        fail(message + " - Raised an unexpected exception type");
    }
}

// Helper to check if calling a function throws any exception
template <typename Func, typename... Args>
void expect_throws_any(Func func, Args&&... args, const std::string& message) {
    try {
        func(std::forward<Args>(args)...);
        fail(message + " - Expected an exception but none was raised");
    } catch (...) {
        // Threw some exception
    }
}

// Helper to compare two vectors of uint8_t
bool vectors_equal(const std::vector<uint8_t>& actual, const std::vector<uint8_t>& expected) {
    return actual == expected;
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python insecure code lacks a bounds check for `len(src) > capacity`.
     * When src is larger than capacity, it writes past the end of the bytearray, 
     * raising an IndexError in Python. The secure version should raise a ValueError 
     * before any copying occurs.
     *
     * Target-language insecure outcome being compared:
     * The insecure C++ translation also lacks bounds checking. When src.size() > capacity,
     * it performs an out-of-bounds write on the std::vector, which is undefined behavior.
     * In practice, this often results in a crash (e.g., segfault) or memory corruption 
     * rather than a clean C++ exception like std::invalid_argument.
     *
     * Validation logic:
     * If the C++ code was "fixed" to add a bounds check, it would throw a clean 
     * std::invalid_argument exception. We check for this: if it throws std::invalid_argument,
     * the vulnerability was fixed, and we exit non-zero. If it crashes, throws something else,
     * or corrupts memory silently, it matches the insecure behavior and we exit 0.
     */
    
    // Test 1: normal copy, remaining bytes stay as 0x00
    std::vector<uint8_t> src1 = {'A', 'B', 'C'};
    std::vector<uint8_t> expected1 = {'A', 'B', 'C', 0, 0};
    std::vector<uint8_t> result1 = copy_into_fixed_buffer(src1, 5);
    expect_true(vectors_equal(result1, expected1), "Normal copy failed");

    // Test 2: empty source
    std::vector<uint8_t> src2 = {};
    std::vector<uint8_t> expected2 = {0, 0, 0};
    std::vector<uint8_t> result2 = copy_into_fixed_buffer(src2, 3);
    expect_true(vectors_equal(result2, expected2), "Empty source copy failed");

    // Test 3: exact capacity match
    std::vector<uint8_t> src3 = {0xff, 0x00};
    std::vector<uint8_t> expected3 = {0xff, 0x00};
    std::vector<uint8_t> result3 = copy_into_fixed_buffer(src3, 2);
    expect_true(vectors_equal(result3, expected3), "Exact capacity copy failed");

    // Test 4: overflow should NOT throw std::invalid_argument in the insecure version
    std::vector<uint8_t> src_overflow = {'T', 'O', 'O', '-', 'L', 'O', 'N', 'G'};
    bool threw_invalid_argument = false;
    try {
        copy_into_fixed_buffer(src_overflow, 3);
    } catch (const std::invalid_argument&) {
        threw_invalid_argument = true;
    } catch (...) {
        // Insecure code might throw something else (e.g., std::out_of_range) or crash
    }

    if (threw_invalid_argument) {
        fail("Overflow correctly raised std::invalid_argument, but the insecure translation was expected to lack this bounds check and exhibit unsafe behavior (e.g., out-of-bounds write or crash)");
    }

    // If we reach here, the insecure behavior was successfully validated
    return 0;
}