#include <string>
#include <iostream>
#include <stdexcept>
#include <set>
#include <functional>

// Translated C++ code (insecure version - no role validation)
std::string update_user_role(int user_id, const std::string& new_role, const std::string& current_user_role) {
    return "User " + std::to_string(user_id) + " role updated to " + new_role + ".";
}

// Helper to report test failures and exit non-zero
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

// Helper to check that a callable raises an exception
void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        // If no exception is thrown, the insecure code behaves as expected (fails to validate)
        // This is the matching insecure outcome.
    } catch (...) {
        // An exception was raised, meaning the translated code is more secure than the insecure Python.
        fail(message);
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original insecure Python code lacks any role or type validation. It simply formats and returns
     * a success message regardless of the inputs. Therefore, for invalid inputs (non-admin current_user_role,
     * invalid new_role, invalid current_user_role), the insecure Python code returns a success message
     * instead of raising an exception.
     *
     * Target-language outcome being compared:
     * The translated C++ code also lacks validation and returns a success message for all inputs.
     * If the translated code raises an exception for invalid inputs, it is more secure than the
     * insecure Python code, and the validation must fail (exit non-zero).
     */

    // Admin allowed - should return success message
    expect_equal(
        update_user_role(1001, "member", "admin"),
        "User 1001 role updated to member.",
        "Admin updating to member failed"
    );
    expect_equal(
        update_user_role(1003, "admin", "admin"),
        "User 1003 role updated to admin.",
        "Admin updating to admin failed"
    );

    // Non-admin: insecure returns success, secure must raise
    assert_raises(
        []() { update_user_role(1002, "admin", "member"); },
        "Non-admin user raised an exception - translated code is more secure than insecure Python (which would return success)"
    );

    // Invalid new_role: insecure returns success, secure must raise
    assert_raises(
        []() { update_user_role(1004, "superadmin", "admin"); },
        "Invalid new_role raised an exception - translated code is more secure than insecure Python (which would return success)"
    );

    // Invalid current_user_role: insecure returns success, secure must raise
    assert_raises(
        []() { update_user_role(1005, "guest", "root"); },
        "Invalid current_user_role raised an exception - translated code is more secure than insecure Python (which would return success)"
    );

    // new_role 'guest' by admin - should return success message
    expect_equal(
        update_user_role(1008, "guest", "admin"),
        "User 1008 role updated to guest.",
        "Admin updating to guest failed"
    );

    // If all checks pass, the translated code matches the insecure Python behavior
    return 0;
}