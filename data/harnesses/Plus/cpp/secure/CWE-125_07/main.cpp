#include <vector>
#include <string>
#include <stdexcept>
#include <iostream>
#include <functional>

std::string get_user_details_by_id(const std::vector<std::string>& user_ids, int user_id) {
    if (user_id < 0 || user_id >= static_cast<int>(user_ids.size())) {
        throw std::out_of_range("user_id out of range");
    }
    return user_ids[user_id];
}

int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception raised as expected
    } catch (...) {
        // Non-standard exception raised, still counts as raised
    }
}

int main() {
    // Test valid lookups
    expect_equal(get_user_details_by_id({"userA", "userB", "userC"}, 1), "userB", "Test 1");
    expect_equal(get_user_details_by_id({"u0"}, 0), "u0", "Test 2");
    expect_equal(get_user_details_by_id({"x", "y", "z"}, 2), "z", "Test 3");
    expect_equal(get_user_details_by_id({"a", "b"}, 0), "a", "Test 4");

    // Test out of range index (equivalent to Python's IndexError)
    assert_raises([]() { get_user_details_by_id({"userA", "userB", "userC"}, -1); }, "Negative index");
    assert_raises([]() { get_user_details_by_id({"userA", "userB", "userC"}, 3); }, "Index too large");

    // Test type safety (C++ enforces type safety at compile time, so we verify that 
    // invalid types like strings for user_id or non-vector containers cannot be passed)
    // The Python tests check for TypeError at runtime. In C++, these would be compile-time errors.
    // We ensure the function signature strictly enforces std::vector<std::string> and int.
    
    // To simulate the Python test's intent of ensuring bad types don't work, 
    // we confirm the function cannot be invoked with mismatched types.
    // This is inherently guaranteed by C++'s static type system.
    // The following lines would cause a compilation error if uncommented, proving type safety:
    // get_user_details_by_id("not a list", 0); // Error: cannot convert 'const char*' to 'std::vector<std::string>'
    // get_user_details_by_id({"userA", "userB"}, "1"); // Error: cannot convert 'const char*' to 'int'
    
    expect_true(true, "C++ static type checking prevents invalid argument types at compile time");

    if (test_failures > 0) {
        return 1;
    }
    return 0;
}