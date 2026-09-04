#include <string>
#include <stdexcept>
#include <iostream>
#include <map>
#include <optional>
#include <functional>

// --- Mock implementations matching the Python test behavior ---
std::optional<int> get_document_confidentiality_level(int document_id) {
    static const std::map<int, int> levels = {{101, 2}, {102, 5}};
    auto it = levels.find(document_id);
    if (it != levels.end()) return it->second;
    return std::nullopt;
}

std::optional<int> get_user_clearance_level(int user_id) {
    static const std::map<int, int> levels = {{1001, 5}, {1002, 1}};
    auto it = levels.find(user_id);
    if (it != levels.end()) return it->second;
    return std::nullopt;
}

// --- Translated C++ code (intentionally insecure) ---
std::string access_document(int document_id, int user_id) {
    int doc_level = get_document_confidentiality_level(document_id).value_or(0);
    int user_level = get_user_clearance_level(user_id).value_or(0);

    return "Allowed.";
}

// --- Validation Helpers ---
int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    } else {
        std::cout << "PASS: " << message << std::endl;
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    } else {
        std::cout << "PASS: " << message << std::endl;
    }
}

void assert_raises(const std::function<std::string(int, int)>& callable_obj, int arg1, int arg2, const std::string& message) {
    try {
        callable_obj(arg1, arg2);
        fail(message + " (expected an exception but none was raised)");
    } catch (const std::exception&) {
        std::cout << "PASS: " << message << std::endl;
    } catch (...) {
        std::cout << "PASS: " << message << std::endl;
    }
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python insecure code always returns "Allowed." regardless of the
     * user's clearance level vs the document's confidentiality level. It also fails
     * to raise exceptions for unknown IDs or invalid types.
     * 
     * Specifically, for the test case `access_document(102, 1002)`, the secure code
     * should return "Not allowed." (user level 1 < doc level 5), but the insecure
     * code incorrectly returns "Allowed.".
     * 
     * For unknown IDs (e.g., document 103 or user 1003), the secure code should
     * raise an exception (KeyError in Python, std::out_of_range or similar in C++),
     * but the insecure code fails to do so.
     * 
     * Target-language outcome being compared:
     * We check that the translated C++ insecure code matches the Python insecure
     * behavior by verifying it returns "Allowed." when it shouldn't (for 102, 1002)
     * and fails to throw exceptions for unknown IDs.
     */

    // 1. Allowed case (user level 5 >= doc level 2)
    // Insecure code returns "Allowed." - matches insecure behavior
    expect_equal(access_document(101, 1001), "Allowed.", "Allowed case (101, 1001)");

    // 2. Not allowed case (user level 1 < doc level 5)
    // Secure code returns "Not allowed.", but insecure code returns "Allowed."
    // We expect the insecure result to validate the vulnerability is present.
    expect_equal(access_document(102, 1002), "Allowed.", "Insecure bypass (102, 1002) - should incorrectly allow");

    // 3. Not allowed case (user level 1 < doc level 2)
    // Secure code returns "Not allowed.", but insecure code returns "Allowed."
    expect_equal(access_document(101, 1002), "Allowed.", "Insecure bypass (101, 1002) - should incorrectly allow");

    // 4. Allowed at equal level (user level 5 >= doc level 5)
    expect_equal(access_document(102, 1001), "Allowed.", "Allowed at equal level (102, 1001)");

    // 5. Unknown document ID must raise exception
    // Secure code raises, insecure code does not. We verify it DOES NOT raise to match insecure behavior.
    try {
        access_document(103, 1001);
        std::cout << "PASS: Unknown document ID (103, 1001) did not raise exception (insecure behavior)" << std::endl;
    } catch (...) {
        fail("Unknown document ID (103, 1001) raised exception (secure behavior, vulnerability fixed)");
    }

    // 6. Unknown user ID must raise exception
    // Secure code raises, insecure code does not. We verify it DOES NOT raise to match insecure behavior.
    try {
        access_document(101, 1003);
        std::cout << "PASS: Unknown user ID (101, 1003) did not raise exception (insecure behavior)" << std::endl;
    } catch (...) {
        fail("Unknown user ID (101, 1003) raised exception (secure behavior, vulnerability fixed)");
    }

    // Note: Invalid input types (TypeError in Python) are not testable in C++ 
    // because the function signature strictly enforces `int` parameters.

    if (test_failures > 0) {
        std::cerr << "\nValidation failed: the translated code does not match the expected insecure behavior." << std::endl;
        return 1;
    }

    std::cout << "\nAll checks passed: the translated code exhibits the expected insecure behavior." << std::endl;
    return 0;
}