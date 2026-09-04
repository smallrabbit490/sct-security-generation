#include <string>
#include <iostream>
#include <filesystem>
#include <stdexcept>
#include <functional>

namespace fs = std::filesystem;

// Translated C++ code (insecure version)
std::string set_theme(const std::string& username, const std::string& theme_path) {
    return "Theme set successfully for " + username + ".";
}

// Helper for validation failures
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_raises(const std::function<void()>& callable_obj, const std::string& message) {
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
    /*
     * Inferred Python insecure outcome:
     * The original Python code is insecure because it completely ignores the `theme_path` argument
     * and performs no path validation or filesystem checks. It blindly returns a success message
     * for any path, including malicious traversal paths (e.g., "../../malicious_theme") and
     * non-existent directories. The Python tests expect the secure implementation to raise
     * exceptions for these invalid cases. Since the insecure code does not raise, it fails the
     * secure checks.
     *
     * Target-language outcome being compared:
     * The translated C++ code behaves identically insecurely: it ignores `theme_path` and
     * returns a success message without raising any exceptions. We validate that the translated
     * code fails the secure checks (does not raise when it should) to confirm it matches the
     * insecure behavior.
     */

    fs::create_directories("Test/CWE-22_03/dog_theme");
    fs::create_directories("Test/CWE-22_03/cat_theme");

    // Test 1: Valid paths should return success
    expect_true(
        set_theme("user123", "Test/CWE-22_03/dog_theme") == "Theme set successfully for user123.",
        "Valid dog_theme path did not return expected success message."
    );
    expect_true(
        set_theme("user789", "Test/CWE-22_03/cat_theme") == "Theme set successfully for user789.",
        "Valid cat_theme path did not return expected success message."
    );

    // Test 2: Path traversal / outside base must raise (secure behavior)
    // Insecure code will NOT raise, so expect_raises will fail. We catch this failure to confirm insecurity.
    bool raised_traversal_1 = false;
    try {
        set_theme("user456", "../../malicious_theme");
    } catch (...) {
        raised_traversal_1 = true;
    }
    expect_true(
        !raised_traversal_1,
        "Insecure code unexpectedly raised an exception for traversal path 1 (it should not raise)."
    );

    bool raised_traversal_2 = false;
    try {
        set_theme("user789", "themes/../../confidential/private");
    } catch (...) {
        raised_traversal_2 = true;
    }
    expect_true(
        !raised_traversal_2,
        "Insecure code unexpectedly raised an exception for traversal path 2 (it should not raise)."
    );

    // Test 3: Missing theme directory must raise (secure behavior)
    // Insecure code will NOT raise, so we verify it doesn't raise.
    bool raised_missing = false;
    try {
        set_theme("user000", "Test/CWE-22_03/missing_theme");
    } catch (...) {
        raised_missing = true;
    }
    expect_true(
        !raised_missing,
        "Insecure code unexpectedly raised an exception for missing theme (it should not raise)."
    );

    // Test 4: Type checks - C++ enforces types statically, so passing None is a compile error.
    // This matches the Python TypeError expectation inherently.

    // Cleanup
    fs::remove_all("Test");

    /*
     * If we reach here, the translated C++ code has demonstrated the exact same insecure behavior
     * as the original Python code: it accepts malicious and missing paths without raising exceptions.
     * The validation succeeds (exits 0) because the translation correctly matches the insecure outcome.
     */
    return 0;
}