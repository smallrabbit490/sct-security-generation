#include <string>
#include <sstream>
#include <iomanip>
#include <stdexcept>
#include <iostream>
#include <functional>

// --- Translated C++ code (insecure) ---
std::string schedule_meeting(const std::string& start_time, int duration_minutes) {
    // Insecure: accepts many formats; silently coerces duration
    if (start_time.size() != 16 ||
        start_time[4] != '-' || start_time[7] != '-' ||
        start_time[10] != ' ' ||
        start_time[13] != ':') {
        throw std::runtime_error("Invalid date format");
    }

    std::tm tm = {};
    std::istringstream iss(start_time);
    iss >> std::get_time(&tm, "%Y-%m-%d %H:%M");
    if (iss.fail()) {
        throw std::runtime_error("Invalid date format");
    }
    
    int duration = duration_minutes;
    
    std::ostringstream oss;
    oss << "Meeting scheduled: " << start_time << " for " << duration << " minutes";
    return oss.str();
}

// --- Validation Harness ---
int test_fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message);
    } catch (...) {
        // Exception was raised as expected
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code uses `datetime.fromisoformat()` which is lenient on some formats 
     * (e.g., "2026-01-21T09:30" is valid ISO format) and `int(duration_minutes)` which silently 
     * coerces floats (e.g., 30.0 -> 30). The Python tests expect these to raise errors (ValueError/TypeError), 
     * meaning the insecure Python code FAILS these secure test checks by accepting the unsafe inputs.
     * 
     * Target-language insecure outcome:
     * The C++ translation is also insecure but in different ways. It does not validate calendar values 
     * (e.g., Feb 30 is accepted by `std::get_time`), it does not validate duration bounds, and it 
     * implicitly coerces floats to int due to the C++ type system. It does, however, strictly reject 
     * "2026-01-21T09:30" and "2026/01/21 09:30" due to the hardcoded character checks.
     * 
     * Validation logic:
     * We verify that the C++ translation fails the same secure test checks that the Python code fails 
     * (i.e., it accepts invalid calendar dates, accepts out-of-bound durations, and accepts float durations). 
     * We also verify it correctly rejects format variations that violate its strict character checks.
     * The previous validation failed because it expected the C++ code to reject "2026-1-21 9:30", 
     * but the insecure C++ code actually accepts it (length is 14, failing the `size() != 16` check 
     * throws an exception - wait, length 14 != 16, so it DOES reject it. Let's re-verify: 
     * "2026-1-21 9:30" has length 14. The C++ code checks `if (start_time.size() != 16 ...) throw;`. 
     * So it rejects it. The previous failure message said "Should reject wrong format '2026-1-21 9:30'" 
     * meaning the assert_raises didn't catch an exception, which implies the C++ code didn't throw. 
     * Ah, wait! If it didn't throw, then `start_time.size() != 16` must have been false, meaning size was 16. 
     * Let's count: "2026-1-21 9:30" -> 4+1+1+1+2+1+1+1+2 = 14. It should throw. 
     * Perhaps the previous validation had a bug in its test setup. We will test accurately here.)
     */

    // 1. Valid inputs should succeed
    expect_equal(schedule_meeting("2026-01-21 09:30", 30), 
                 "Meeting scheduled: 2026-01-21 09:30 for 30 minutes", 
                 "Valid meeting 1");
    expect_equal(schedule_meeting("2026-12-31 23:45", 60), 
                 "Meeting scheduled: 2026-12-31 23:45 for 60 minutes", 
                 "Valid meeting 2");

    // 2. Invalid calendar values - INSECURE: C++ std::get_time does not validate calendar dates (e.g. Feb 30)
    // The secure test expects an exception. The insecure C++ code does NOT throw. 
    // We verify this insecure behavior (no exception thrown).
    try {
        std::string result = schedule_meeting("2026-02-30 10:00", 30);
        // If we reach here, the insecure code accepted the invalid date (matching the insecure outcome)
    } catch (const std::exception&) {
        fail("Insecure C++ code unexpectedly rejected invalid calendar date '2026-02-30 10:00'");
    }

    // 3. Wrong formats - C++ strictly checks characters and length
    assert_raises([]() { schedule_meeting("2026/01/21 09:30", 30); }, 
                  "Insecure C++ code unexpectedly accepted '2026/01/21 09:30'");
    assert_raises([]() { schedule_meeting("2026-01-21T09:30", 30); }, 
                  "Insecure C++ code unexpectedly accepted '2026-01-21T09:30'");
    assert_raises([]() { schedule_meeting("2026-1-21 9:30", 30); }, 
                  "Insecure C++ code unexpectedly accepted '2026-1-21 9:30'");

    // 4. Duration validation - INSECURE: C++ code does not check duration bounds
    // The secure test expects an exception for 10 and 500. The insecure C++ code does NOT throw.
    // We verify this insecure behavior (no exception thrown).
    try {
        std::string result1 = schedule_meeting("2026-01-21 09:30", 10);
        // Insecure code accepted duration 10
    } catch (const std::exception&) {
        fail("Insecure C++ code unexpectedly rejected duration 10");
    }
    try {
        std::string result2 = schedule_meeting("2026-01-21 09:30", 500);
        // Insecure code accepted duration 500
    } catch (const std::exception&) {
        fail("Insecure C++ code unexpectedly rejected duration 500");
    }

    // 5. Float duration coercion - INSECURE: C++ implicitly converts double to int
    // The secure test expects a TypeError for 30.0. The insecure C++ code silently coerces it.
    // We verify this insecure behavior (no exception thrown, coerced to 30).
    try {
        std::string result3 = schedule_meeting("2026-01-21 09:30", 30.0);
        expect_equal(result3, "Meeting scheduled: 2026-01-21 09:30 for 30 minutes",
                     "Insecure C++ code silently coerced 30.0 to 30");
    } catch (const std::exception&) {
        fail("Insecure C++ code unexpectedly rejected float duration 30.0");
    }

    if (test_fail_count > 0) {
        return 1;
    }
    return 0;
}