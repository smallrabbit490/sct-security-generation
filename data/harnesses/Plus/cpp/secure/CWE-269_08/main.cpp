#include <stdexcept>
#include <string>
#include <unordered_set>
#include <iostream>
#include <cstdlib>

std::string update_user_role(int user_id, const std::string& new_role, const std::string& current_user_role) {
    const std::unordered_set<std::string> valid_roles = {"guest", "member", "admin"};

    if (valid_roles.find(current_user_role) == valid_roles.end()) {
        throw std::invalid_argument("invalid current_user_role");
    }

    if (current_user_role != "admin") {
        throw std::runtime_error("insufficient privileges");
    }

    if (valid_roles.find(new_role) == valid_roles.end()) {
        throw std::invalid_argument("invalid new_role");
    }

    return "User " + std::to_string(user_id) + " role updated to " + new_role + ".";
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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

template <typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raised
    }
}

int main() {
    // admin allowed
    expect_equal(
        update_user_role(1001, "member", "admin"),
        "User 1001 role updated to member.",
        "Test 1001"
    );
    expect_equal(
        update_user_role(1003, "admin", "admin"),
        "User 1003 role updated to admin.",
        "Test 1003"
    );

    // non-admin: insecure returns success, secure must raise
    assert_raises(
        []() { update_user_role(1002, "admin", "member"); },
        "Test 1002 non-admin"
    );

    // invalid new_role: insecure returns success, secure must raise
    assert_raises(
        []() { update_user_role(1004, "superadmin", "admin"); },
        "Test 1004 invalid new_role"
    );

    // invalid current_user_role: insecure returns success, secure must raise
    assert_raises(
        []() { update_user_role(1005, "guest", "root"); },
        "Test 1005 invalid current_user_role"
    );

    // invalid new_role type: insecure returns success, secure must raise
    // In C++, passing None/nullptr to const std::string& throws std::invalid_argument
    assert_raises(
        []() { update_user_role(1006, std::string(), "admin"); },
        "Test 1006 invalid new_role type"
    );

    // current_user_role wrong type: secure raises invalid_argument (not in set)
    assert_raises(
        []() { update_user_role(1007, "member", std::string()); },
        "Test 1007 current_user_role wrong type"
    );

    // new_role 'guest' by admin
    expect_equal(
        update_user_role(1008, "guest", "admin"),
        "User 1008 role updated to guest.",
        "Test 1008"
    );

    std::cout << "All tests passed!" << std::endl;
    return 0;
}