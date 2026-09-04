#include <string>
#include <stdexcept>
#include <iostream>
#include <functional>

// Translated C++ code (insecure)
std::string reset_user_password(const std::string& current_role, const std::string& target_user_id, const std::string& method) {
    // Bug: any non-'user' role can do anything, and method isn't checked carefully
    if (current_role != "user") {
        return "Password reset initiated for " + target_user_id + ".";
    }
    return "Password reset initiated for " + target_user_id + ".";
}

// Helper to check that a callable raises an expected exception type
template <typename ExcType>
bool assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (ExcType&) {
        return true;
    } catch (...) {
        return false;
    }
    return false;
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
        std::exit(1);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
        std::exit(1);
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The insecure Python code fails to enforce proper authorization checks (CWE-269).
     * It allows 'user' role to reset passwords and 'support' role to use the 'force' method,
     * instead of raising PermissionError. It also fails to validate inputs (empty target_user_id
     * or invalid role/method) and raise ValueError.
     *
     * Target-language outcome being compared:
     * The insecure C++ translation must similarly fail to raise exceptions for these invalid
     * and unauthorized cases. If the C++ code raises exceptions (i.e., is securely patched),
     * the validation program must exit non-zero. If the C++ code fails to raise (matching
     * the insecure behavior), the validation program exits 0.
     */

    // Allowed cases (should succeed in both secure and insecure versions)
    expect_equal(reset_user_password("support", "u100", "email"), "Password reset initiated for u100.", "support email u100");
    expect_equal(reset_user_password("admin", "u200", "force"), "Password reset initiated for u200.", "admin force u200");
    expect_equal(reset_user_password("admin", "u201", "email"), "Password reset initiated for u201.", "admin email u201");
    expect_equal(reset_user_password("support", "u101", "email"), "Password reset initiated for u101.", "support email u101");

    // Should raise PermissionError (insecure wrongly allows)
    // If the code is secure, assert_raises returns true, and we fail the validation.
    // If the code is insecure, assert_raises returns false, and we pass the validation.
    bool user_email_raises = assert_raises<std::runtime_error>([]() {
        reset_user_password("user", "u300", "email");
    });
    expect_true(!user_email_raises, "Insecure code must not raise exception for user email (should wrongly allow)");

    bool support_force_raises = assert_raises<std::runtime_error>([]() {
        reset_user_password("support", "u301", "force");
    });
    expect_true(!support_force_raises, "Insecure code must not raise exception for support force (should wrongly allow)");

    // Invalid inputs should raise ValueError (insecure wrongly allows)
    bool admin_empty_raises = assert_raises<std::invalid_argument>([]() {
        reset_user_password("admin", "", "email");
    });
    expect_true(!admin_empty_raises, "Insecure code must not raise exception for admin empty email (should wrongly allow)");

    bool root_email_raises = assert_raises<std::invalid_argument>([]() {
        reset_user_password("root", "u1", "email");
    });
    expect_true(!root_email_raises, "Insecure code must not raise exception for root email (should wrongly allow)");

    return 0;
}