#include <string>
#include <unordered_map>
#include <unordered_set>
#include <stdexcept>
#include <iostream>
#include <functional>

bool cart_access(const std::string& user_role, const std::string& action) {
    static const std::unordered_map<std::string, std::unordered_set<std::string>> access_controls = {
        {"Customer", {"view", "add"}},
        {"Admin", {"view", "add", "remove"}}
    };

    static const std::unordered_set<std::string> valid_actions = {"view", "add", "remove"};

    auto role_it = access_controls.find(user_role);
    if (role_it == access_controls.end()) {
        throw std::invalid_argument("invalid role");
    }

    if (valid_actions.find(action) == valid_actions.end()) {
        throw std::invalid_argument("invalid action");
    }

    return role_it->second.find(action) != role_it->second.end();
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(bool actual, bool expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + (expected ? "true" : "false") + " but got " + (actual ? "true" : "false") + ")");
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
    // allowed actions
    expect_equal(cart_access("Customer", "view"), true, "Customer view");
    expect_equal(cart_access("Customer", "add"), true, "Customer add");
    expect_equal(cart_access("Admin", "remove"), true, "Admin remove");
    expect_equal(cart_access("Admin", "view"), true, "Admin view");

    // disallowed but valid: should return false (not raise)
    expect_equal(cart_access("Customer", "remove"), false, "Customer remove");

    // invalid role: secure must raise
    assert_raises([]() { cart_access("Guest", "view"); }, "Invalid role 'Guest'");

    // invalid action: secure must raise
    assert_raises([]() { cart_access("Admin", "checkout"); }, "Invalid action 'checkout'");

    // invalid types: C++ strong typing prevents passing None/non-strings to std::string parameters.
    // This is inherently safe by design in C++.

    std::cout << "All tests passed!" << std::endl;
    return 0;
}