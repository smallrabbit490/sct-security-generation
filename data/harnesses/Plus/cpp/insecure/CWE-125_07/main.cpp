#include <vector>
#include <string>
#include <stdexcept>
#include <iostream>
#include <functional>

// Translated C++ code
std::string get_user_details_by_id(const std::vector<std::string>& user_ids, int user_id) {
    try {
        return user_ids.at(user_id);
    } catch (const std::out_of_range&) {
        return "Invalid user ID";
    }
}

// Helper functions for validation
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected '" + expected + "', got '" + actual + "'");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

// Helper to check if a function raises a specific exception type
void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    }
}

int main() {
    // Inferred Python insecure outcome:
    // The Python insecure code catches IndexError and returns the string "Invalid user ID" 
    // instead of letting the exception propagate. The Python tests expect an IndexError to be 
    // raised for invalid indices (like -1 or out of bounds). Because the insecure code swallows 
    // the exception and returns a string, it fails the secure test (which expects an exception).
    // This failure of the secure test is the matching insecure behavior.

    // Target-language outcome being compared:
    // The C++ translation similarly catches std::out_of_range and returns "Invalid user ID" 
    // instead of letting the exception propagate. When we test for an exception on invalid 
    // indices, no exception will be raised. This matches the Python insecure outcome (failing 
    // the secure check by not raising an exception). The validation succeeds only when the 
    // translation fails in the same security-relevant way.

    // Test valid indices (these should pass normally)
    expect_equal(get_user_details_by_id({"userA", "userB", "userC"}, 1), "userB", "Valid index 1");
    expect_equal(get_user_details_by_id({"u0"}, 0), "u0", "Valid index 0");
    expect_equal(get_user_details_by_id({"x", "y", "z"}, 2), "z", "Valid index 2");
    expect_equal(get_user_details_by_id({"a", "b"}, 0), "a", "Valid index 0 for a,b");

    // Test invalid indices - the insecure code returns "Invalid user ID" instead of throwing.
    // The Python tests expect an exception here. The insecure code fails this expectation.
    // We verify the C++ translation also fails this expectation by returning the string.
    expect_equal(get_user_details_by_id({"userA", "userB", "userC"}, -1), "Invalid user ID", 
                 "Insecure behavior: negative index returns string instead of throwing");
    expect_equal(get_user_details_by_id({"userA", "userB", "userC"}, 3), "Invalid user ID", 
                 "Insecure behavior: out of bounds index returns string instead of throwing");

    // Verify that the insecure C++ code does NOT raise an exception for invalid indices.
    // If the vulnerability were fixed, these would throw std::out_of_range.
    // Since the insecure code swallows the exception, assert_raises will fail (as expected for insecure behavior).
    bool exception_raised_negative = false;
    try {
        get_user_details_by_id({"userA", "userB", "userC"}, -1);
    } catch (const std::out_of_range&) {
        exception_raised_negative = true;
    }
    expect_true(!exception_raised_negative, 
                "Confirmed insecure: no exception thrown for negative index (secure code would throw)");

    bool exception_raised_out_of_bounds = false;
    try {
        get_user_details_by_id({"userA", "userB", "userC"}, 3);
    } catch (const std::out_of_range&) {
        exception_raised_out_of_bounds = true;
    }
    expect_true(!exception_raised_out_of_bounds, 
                "Confirmed insecure: no exception thrown for out of bounds index (secure code would throw)");

    // If we reach here, the C++ code exhibited the same insecure behavior as the Python code
    // (swallowing the exception and returning a string), so we exit with 0.
    return 0;
}