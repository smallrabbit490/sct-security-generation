#include <string>
#include <stdexcept>
#include <iostream>

// Translated insecure C++ code:
// The original Python insecure code returns 'Read-only access granted' for any
// non-admin role (including invalid ones) instead of raising an exception.
// The translated C++ code mirrors this insecure behavior by returning
// 'Read-only access granted' for any non-admin role without throwing.
std::string grant_access(const std::string& role) {
    if (role == "admin") {
        return "Full access granted";
    } else {
        return "Read-only access granted";
    }
}

// Helper functions for the validation harness
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
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

// Helper to check that grant_access does NOT throw for a given input
void expect_no_throw(const std::string& role, const std::string& message) {
    try {
        grant_access(role);
    } catch (const std::exception& e) {
        fail(message + " - exception thrown: " + e.what());
    } catch (...) {
        fail(message + " - unknown exception thrown");
    }
}

int main() {
    // Inferred Python insecure outcome:
    // The insecure Python code returns 'Read-only access granted' for invalid roles
    // (e.g., 'invalid_role', 'Admin', '', '   ') instead of raising a ValueError.
    // It also does not raise a TypeError for None (though C++ type safety prevents None).
    
    // Target-language outcome being compared:
    // The insecure C++ translation must similarly return 'Read-only access granted'
    // for invalid roles without throwing any exception. If it throws (i.e., the 
    // vulnerability is fixed), the validation program must exit non-zero.

    // 1. Valid roles should return correct strings
    expect_equal(grant_access("admin"), "Full access granted", "admin should get Full access granted");
    expect_equal(grant_access("guest"), "Read-only access granted", "guest should get Read-only access granted");

    // 2. Invalid roles: insecure code returns 'Read-only access granted' without throwing
    // If the vulnerability is fixed, grant_access would throw, and these checks will fail the validation.
    expect_no_throw("invalid_role", "insecure code should not throw for invalid_role");
    expect_equal(grant_access("invalid_role"), "Read-only access granted", "insecure code should return Read-only for invalid_role");

    expect_no_throw("Admin", "insecure code should not throw for case mismatch Admin");
    expect_equal(grant_access("Admin"), "Read-only access granted", "insecure code should return Read-only for case mismatch Admin");

    expect_no_throw("", "insecure code should not throw for empty role");
    expect_equal(grant_access(""), "Read-only access granted", "insecure code should return Read-only for empty role");

    expect_no_throw("   ", "insecure code should not throw for whitespace role");
    expect_equal(grant_access("   "), "Read-only access granted", "insecure code should return Read-only for whitespace role");

    return 0;
}