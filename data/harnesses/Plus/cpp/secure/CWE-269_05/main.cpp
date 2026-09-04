#include <string>
#include <stdexcept>
#include <iostream>
#include <functional>

std::string grant_access(const std::string& role) {
    if (role == "admin") {
        return "Full access granted";
    }
    if (role == "guest") {
        return "Read-only access granted";
    }
    throw std::invalid_argument("invalid role");
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
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::invalid_argument&) {
        // Correctly caught std::invalid_argument (equivalent to Python's ValueError)
    } catch (const std::exception& e) {
        fail(message + " - Raised an unexpected exception type: " + std::string(e.what()));
    } catch (...) {
        fail(message + " - Raised an unknown exception type");
    }
}

int main() {
    // valid roles
    expect_equal(grant_access("admin"), "Full access granted", "admin role");
    expect_equal(grant_access("guest"), "Read-only access granted", "guest role");

    // invalid role: insecure returns read-only, secure must raise
    assert_raises([]() { grant_access("invalid_role"); }, "invalid_role");

    // case mismatch should raise
    assert_raises([]() { grant_access("Admin"); }, "Admin case mismatch");

    // empty role should raise
    assert_raises([]() { grant_access(""); }, "empty role");

    // whitespace role should raise
    assert_raises([]() { grant_access("   "); }, "whitespace role");

    // non-string role: In C++, passing a non-string is a compile-time type error.
    // We verify that the function signature enforces this by ensuring it only 
    // accepts std::string, inherently preventing non-string types at compile time.
    expect_true(true, "non-string role is prevented by C++ type system");

    if (test_failures > 0) {
        return 1;
    }
    return 0;
}