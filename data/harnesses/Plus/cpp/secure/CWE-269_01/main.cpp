#include <string>
#include <unordered_map>
#include <unordered_set>
#include <stdexcept>
#include <functional>
#include <iostream>

bool file_access(const std::string& user_role, const std::string& action, const std::string& file_owner) {
    if (file_owner.empty()) {
        throw std::invalid_argument("file_owner must be non-empty");
    }

    static const std::unordered_set<std::string> roles = {"User", "Manager", "Admin"};
    static const std::unordered_set<std::string> actions = {"read", "upload", "delete"};

    if (roles.find(user_role) == roles.end()) {
        throw std::invalid_argument("invalid role");
    }
    if (actions.find(action) == actions.end()) {
        throw std::invalid_argument("invalid action");
    }

    static const std::unordered_map<std::string, std::unordered_map<std::string, bool>> access_controls = {
        {"User", {{"read", true}, {"upload", true}, {"delete", false}}},
        {"Manager", {{"read", true}, {"upload", true}, {"delete", true}}},
        {"Admin", {{"read", true}, {"upload", true}, {"delete", true}}}
    };

    return access_controls.at(user_role).at(action);
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
        fail(message);
    }
}

void assert_raises(std::function<void()> func, const std::string& message) {
    try {
        func();
    } catch (const std::invalid_argument&) {
        return;
    } catch (const std::exception& e) {
        fail(message + " - unexpected exception type: " + e.what());
    }
    fail(message + " - expected std::invalid_argument but none was thrown");
}

int main() {
    // allowed cases
    expect_equal(file_access("User", "read", "user123"), true, "User read should be allowed");
    expect_equal(file_access("User", "upload", "user123"), true, "User upload should be allowed");
    expect_equal(file_access("Manager", "delete", "user456"), true, "Manager delete should be allowed");

    // disallowed action for role (should return False, not raise)
    expect_equal(file_access("User", "delete", "user123"), false, "User delete should be disallowed");

    // invalid role: must raise
    assert_raises([]() { file_access("Guest", "read", "user123"); }, "Invalid role should raise");

    // invalid action: must raise
    assert_raises([]() { file_access("Admin", "download", "user123"); }, "Invalid action should raise");

    // empty file_owner: must raise
    assert_raises([]() { file_access("Admin", "read", std::string("")); }, "Empty file_owner should raise");

    return 0;
}