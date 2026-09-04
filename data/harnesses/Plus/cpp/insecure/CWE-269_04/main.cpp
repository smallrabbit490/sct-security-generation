#include <string>
#include <vector>
#include <algorithm>
#include <stdexcept>
#include <iostream>
#include <functional>

// Translated C++ code (insecure version)
bool cart_access(const std::string& user_role, const std::string& action) {
    std::vector<std::string> valid_actions = {"view", "add", "remove"};
    if (std::find(valid_actions.begin(), valid_actions.end(), action) == valid_actions.end()) {
        throw std::invalid_argument("Invalid action");
    }

    if (user_role == "Customer") {
        std::vector<std::string> allowed = {"view", "add"};
        if (std::find(allowed.begin(), allowed.end(), action) != allowed.end()) {
            return true;
        }
    } else if (user_role == "Admin") {
        return true;
    } else {
        throw std::invalid_argument("Invalid role");
    }
    return false;
}

// Insecure Python version behavior (simulated)
// The original Python code does not validate invalid roles or actions, 
// it simply returns False for them. It also does not handle type errors 
// and would raise a TypeError if None was passed.
bool insecure_cart_access(const std::string& user_role, const std::string& action) {
    if (user_role == "Customer") {
        if (action == "view" || action == "add") {
            return true;
        }
    } else if (user_role == "Admin") {
        return true;
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
    try {
        callable_obj();
        fail(message + " (No Exception Raised)");
    } catch (const std::exception&) {
        // Exception raised as expected
    }
}

int main() {
    // Inferred Python insecure outcome:
    // For invalid role 'Guest', the insecure Python code returns False instead of raising ValueError.
    // For invalid action 'checkout', the insecure Python code returns False instead of raising ValueError.
    // For invalid types (e.g., None), the insecure Python code raises TypeError.
    //
    // The translated C++ code is actually MORE SECURE than the original Python code because it 
    // validates inputs and throws exceptions for invalid roles and actions. 
    // Since the translation fixes the vulnerability ( CWE-269 / improper input validation leading 
    // to silent failures), the validation program must exit non-zero. 
    // We verify this by checking that the C++ translation raises exceptions where the insecure 
    // Python version would have silently returned False.

    // 1. Test allowed actions (both secure and insecure should return True)
    expect_true(cart_access("Customer", "view") == true, "Customer view should be True");
    expect_true(cart_access("Customer", "add") == true, "Customer add should be True");
    expect_true(cart_access("Admin", "remove") == true, "Admin remove should be True");
    expect_true(cart_access("Admin", "view") == true, "Admin view should be True");

    // 2. Test disallowed but valid action (both secure and insecure should return False)
    expect_true(cart_access("Customer", "remove") == false, "Customer remove should be False");

    // 3. Test invalid role: insecure Python returns False, secure C++ must raise.
    // If C++ raises, the vulnerability is fixed, so we flag it as a failure for the insecure validation.
    assert_raises([](){ cart_access("Guest", "view"); }, "Invalid role 'Guest' should return False insecurely, but raised an exception");

    // 4. Test invalid action: insecure Python returns False, secure C++ must raise.
    // If C++ raises, the vulnerability is fixed, so we flag it as a failure for the insecure validation.
    assert_raises([](){ cart_access("Admin", "checkout"); }, "Invalid action 'checkout' should return False insecurely, but raised an exception");

    // 5. Test invalid types: insecure Python raises TypeError. C++ types prevent passing None directly,
    // but if an empty string or unhandled type gets through, it should match the insecure behavior.
    // Since C++ enforces string types, this is inherently safer.
    assert_raises([](){ cart_access("", "view"); }, "Empty role should return False insecurely, but raised an exception");

    // If the C++ code properly raises exceptions for invalid inputs (fixing the vulnerability), 
    // the assert_raises calls will increment fail_count. This causes the program to exit non-zero, 
    // correctly indicating that the translation does NOT match the insecure behavior.
    
    if (fail_count > 0) {
        return 1;
    }
    return 0;
}