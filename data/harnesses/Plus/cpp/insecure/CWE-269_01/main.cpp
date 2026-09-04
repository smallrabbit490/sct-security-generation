#include <string>
#include <set>
#include <stdexcept>
#include <iostream>
#include <functional>

// Inferred Python insecure outcome:
// The insecure Python code silently returns False for invalid inputs 
// (invalid role like "Guest", invalid action like "download", empty file_owner, 
// or non-string type like None). The secure version must raise a ValueError or TypeError.
// The C++ translation mirrors this insecure behavior by returning false without throwing.
// The validation succeeds (exits 0) only if the C++ code fails the secure checks 
// (i.e., does NOT throw exceptions for invalid inputs, matching the insecure behavior).

bool file_access(const std::string& user_role, const std::string& action, const std::string& file_owner) {
    if (user_role == "User") {
        std::set<std::string> allowed = {"read", "upload"};
        if (allowed.find(action) != allowed.end()) {
            return user_role == file_owner;
        }
    } else if (user_role == "Manager") {
        std::set<std::string> allowed = {"read", "upload", "delete"};
        if (allowed.find(action) != allowed.end()) {
            return true;
        }
    } else if (user_role == "Admin") {
        std::set<std::string> allowed = {"read", "upload", "delete"};
        if (allowed.find(action) != allowed.end()) {
            return true;
        }
    }
    return false;
}

int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_false(bool condition, const std::string& message) {
    if (condition) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message);
    }
}

int main() {
    // Allowed cases
    expect_true(file_access("User", "read", "user123"), "User read own file");
    expect_true(file_access("User", "upload", "user123"), "User upload own file");
    expect_true(file_access("Manager", "delete", "user456"), "Manager delete file");

    // Disallowed action for role (should return false, not raise)
    expect_false(file_access("User", "delete", "user123"), "User delete disallowed");

    // Insecure behavior checks: the insecure code returns false without throwing.
    // The secure code must throw. We assert that it raises; if it doesn't, 
    // the insecure behavior is confirmed (which is what we want to validate here).
    
    // Invalid role: insecure returns false (no exception), secure must raise
    assert_raises([]() { file_access("Guest", "read", "user123"); }, 
                  "Invalid role did not raise (insecure behavior confirmed)");

    // Invalid action: insecure returns false (no exception), secure must raise
    assert_raises([]() { file_access("Admin", "download", "user123"); }, 
                  "Invalid action did not raise (insecure behavior confirmed)");

    // Empty file_owner: insecure returns false (no exception), secure must raise
    assert_raises([]() { file_access("Admin", "read", ""); }, 
                  "Empty file_owner did not raise (insecure behavior confirmed)");

    // If fail_count > 0, it means the insecure code failed to raise exceptions 
    // for invalid inputs, which matches the expected insecure Python outcome.
    // If fail_count == 0, the code is secure (throws exceptions), so we must exit non-zero.
    if (fail_count > 0) {
        // Insecure behavior matched
        return 0;
    } else {
        // Code is secure, validation fails
        return 1;
    }
}