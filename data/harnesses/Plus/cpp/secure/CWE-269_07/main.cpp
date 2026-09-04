#include <string>
#include <stdexcept>
#include <set>
#include <iostream>
#include <cstdlib>

class PermissionError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

std::string modify_project_access(const std::string& project_id, const std::string& user_id, const std::string& action, const std::string& current_user_role) {
    // In C++, passing arguments as std::string inherently ensures they are strings,
    // satisfying the Python isinstance(x, str) check.

    static const std::set<std::string> valid_actions = {"add", "remove"};
    if (valid_actions.find(action) == valid_actions.end()) {
        throw std::invalid_argument("invalid action");
    }

    static const std::set<std::string> valid_roles = {"guest", "member", "project_manager", "admin"};
    if (valid_roles.find(current_user_role) == valid_roles.end()) {
        throw std::invalid_argument("invalid role");
    }

    static const std::set<std::string> privileged_roles = {"project_manager", "admin"};
    if (privileged_roles.find(current_user_role) == privileged_roles.end()) {
        throw PermissionError("insufficient privileges");
    }

    return "Access rights '" + action + "' for user " + user_id + " in project " + project_id + ".";
}

// Test helpers
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
        fail(message + " - Expected: '" + expected + "', Got: '" + actual + "'");
    }
}

template <typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message + " - Expected an exception but none was raised");
    }
}

int main() {
    // allowed roles
    expect_equal(
        modify_project_access("proj2", "user2", "add", "admin"),
        "Access rights 'add' for user user2 in project proj2.",
        "admin add"
    );
    expect_equal(
        modify_project_access("proj3", "user3", "remove", "project_manager"),
        "Access rights 'remove' for user user3 in project proj3.",
        "project_manager remove"
    );

    // guest: insecure returns "Action completed.", secure must raise
    assert_raises([]() {
        modify_project_access("proj1", "user1", "add", "guest");
    }, "guest add");

    // member: insecure returns success, secure must raise
    assert_raises([]() {
        modify_project_access("proj1", "user1", "remove", "member");
    }, "member remove");

    // invalid action: insecure returns success, secure must raise
    assert_raises([]() {
        modify_project_access("proj1", "user1", "grant", "admin");
    }, "invalid action grant");

    // invalid current_user_role: insecure returns "Action completed.", secure must raise
    assert_raises([]() {
        modify_project_access("proj1", "user1", "add", "superuser");
    }, "invalid role superuser");

    // invalid types (C++ enforces string types at compile time, so we just verify no runtime exception is thrown for valid string calls)
    // The Python test checks for TypeError on None, which is inherently prevented by C++'s static typing.
    // We ensure the function behaves correctly with valid string inputs.
    expect_equal(
        modify_project_access("proj1", "user1", "add", "admin"),
        "Access rights 'add' for user user1 in project proj1.",
        "valid string inputs"
    );

    // empty project_id is still a string; secure allows (no rule against empty), so do a valid call
    expect_equal(
        modify_project_access("", "u", "add", "admin"),
        "Access rights 'add' for user u in project .",
        "empty project_id"
    );

    return 0;
}