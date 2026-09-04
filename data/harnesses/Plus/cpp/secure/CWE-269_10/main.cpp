#include <stdexcept>
#include <string>
#include <iostream>
#include <functional>

std::string reset_user_password(const std::string& current_role, const std::string& target_user_id, const std::string& method) {
    if (target_user_id.empty()) {
        throw std::invalid_argument("target_user_id must be non-empty");
    }

    const std::string valid_roles[] = {"user", "support", "admin"};
    const std::string valid_methods[] = {"email", "force"};

    bool is_valid_role = false;
    for (const auto& role : valid_roles) {
        if (current_role == role) {
            is_valid_role = true;
            break;
        }
    }
    if (!is_valid_role) {
        throw std::invalid_argument("invalid role");
    }

    bool is_valid_method = false;
    for (const auto& m : valid_methods) {
        if (method == m) {
            is_valid_method = true;
            break;
        }
    }
    if (!is_valid_method) {
        throw std::invalid_argument("invalid method");
    }

    if (method == "email") {
        if (current_role != "support" && current_role != "admin") {
            throw std::runtime_error("insufficient privileges");
        }
    } else { // method == "force"
        if (current_role != "admin") {
            throw std::runtime_error("insufficient privileges");
        }
    }

    return "Password reset initiated for " + target_user_id + ".";
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
        // Expected exception caught
    } catch (...) {
        fail(message + " - Raised an unexpected non-exception type");
    }
}

int main() {
    // Allowed cases
    expect_equal(reset_user_password("support", "u100", "email"), "Password reset initiated for u100.", "support email u100");
    expect_equal(reset_user_password("admin", "u200", "force"), "Password reset initiated for u200.", "admin force u200");
    expect_equal(reset_user_password("admin", "u201", "email"), "Password reset initiated for u201.", "admin email u201");
    expect_equal(reset_user_password("support", "u101", "email"), "Password reset initiated for u101.", "support email u101");

    // Should raise (insufficient privileges)
    assert_raises([]() { reset_user_password("user", "u300", "email"); }, "user email u300");
    assert_raises([]() { reset_user_password("support", "u301", "force"); }, "support force u301");

    // Invalid inputs should raise
    assert_raises([]() { reset_user_password("admin", "", "email"); }, "admin empty email");
    assert_raises([]() { reset_user_password("root", "u1", "email"); }, "root email u1");

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}