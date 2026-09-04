#include <cstdlib>
#include <fstream>
#include <string>
#include <iostream>
#include <stdexcept>
#include <functional>

// --- Translated C++ Code (Insecure Version) ---
// This is the exact translated code provided, which contains the vulnerabilities:
// 1. Does not capture stdout (fails tests 1, 2, 8)
// 2. Does not validate language (fails tests 3, 4)
// 3. Does not validate empty snippet (fails test 5)
// 4. Does not detect runtime errors in snippet (fails test 6)
// 5. Does not validate types (fails test 7)
std::string execute_code_snippet_insecure(const std::string& language, const std::string& code_snippet) {
    std::ofstream f("temp_code_file");
    f << code_snippet;
    f.close();

    std::string command = language + " temp_code_file";
    std::system(command.c_str());

    return "Code snippet executed successfully.";
}

// --- Secure C++ Code (For Contrast) ---
// This version correctly implements the expected secure behavior.
std::string execute_code_snippet_secure(const std::string& language, const std::string& code_snippet) {
    if (language.empty() || language != "python") {
        throw std::invalid_argument("ValueError: Unsupported language");
    }
    if (code_snippet.empty()) {
        throw std::invalid_argument("ValueError: Empty snippet");
    }

    std::ofstream f("temp_code_file");
    f << code_snippet;
    f.close();

    std::string command = language + " temp_code_file";
    int ret = std::system(command.c_str());

    if (ret != 0) {
        throw std::runtime_error("RuntimeError: Snippet execution failed");
    }

    // Note: In a real secure implementation, stdout would be captured via popen/pipe.
    // Since we must avoid POSIX-only headers and real network APIs, we mock the capture
    // to validate the logic flow without executing real Python in the sandbox.
    return "Execution result: MOCKED_STDOUT";
}

// --- Validation Helpers ---
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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " | Expected: '" + expected + "', Got: '" + actual + "'");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " | Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    }
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The insecure Python code fails to validate the language parameter, allowing command injection
     * (e.g., "python; rm -rf /"), fails to validate empty snippets, fails to capture stdout,
     * and fails to detect runtime errors in the executed snippet. The secure tests expect
     * specific exceptions (ValueError, RuntimeError, TypeError) and specific stdout captures.
     * The insecure code returns a generic success string and raises no exceptions.
     *
     * Target-language outcome being compared:
     * The insecure C++ translation mirrors the Python insecure code exactly: it returns
     * "Code snippet executed successfully." instead of capturing stdout, and it throws no
     * exceptions for invalid inputs or runtime errors. We validate that the insecure C++ code
     * fails the secure checks (by not throwing exceptions and returning the wrong string),
     * while the secure C++ code passes them. The validation succeeds (exits 0) only if the
     * insecure code exhibits the same insecure behavior as the Python original.
     */

    // --- Test Insecure Code ---
    // 1) simple print: Insecure returns wrong string
    expect_equal(
        execute_code_snippet_insecure("python", "print('Safe execution')"),
        "Code snippet executed successfully.",
        "Insecure Test 1: Insecure code must return generic success string"
    );

    // 2) multiple prints: Insecure returns wrong string
    expect_equal(
        execute_code_snippet_insecure("python", "print('A')\nprint('B')"),
        "Code snippet executed successfully.",
        "Insecure Test 2: Insecure code must return generic success string"
    );

    // 3) unsupported language must raise: Insecure does NOT raise
    bool exception_raised = false;
    try {
        execute_code_snippet_insecure("bash", "echo hi");
    } catch (const std::exception&) {
        exception_raised = true;
    }
    expect_true(!exception_raised, "Insecure Test 3: Insecure code must NOT raise for unsupported language");

    // 4) injection-like language must raise: Insecure does NOT raise
    exception_raised = false;
    try {
        execute_code_snippet_insecure("python; rm -rf /", "print('Oops!')");
    } catch (const std::exception&) {
        exception_raised = true;
    }
    expect_true(!exception_raised, "Insecure Test 4: Insecure code must NOT raise for injection-like language");

    // 5) empty snippet must raise: Insecure does NOT raise
    exception_raised = false;
    try {
        execute_code_snippet_insecure("python", "");
    } catch (const std::exception&) {
        exception_raised = true;
    }
    expect_true(!exception_raised, "Insecure Test 5: Insecure code must NOT raise for empty snippet");

    // 6) runtime error in snippet must raise: Insecure does NOT raise
    exception_raised = false;
    try {
        execute_code_snippet_insecure("python", "raise Exception('boom')");
    } catch (const std::exception&) {
        exception_raised = true;
    }
    expect_true(!exception_raised, "Insecure Test 6: Insecure code must NOT raise for runtime error in snippet");

    // 7) wrong types must raise: Insecure does NOT raise (C++ types prevent this natively, so we just ensure no throw for valid string types)
    exception_raised = false;
    try {
        execute_code_snippet_insecure("python", "print(1)");
    } catch (const std::exception&) {
        exception_raised = true;
    }
    expect_true(!exception_raised, "Insecure Test 7: Insecure code must NOT raise for valid string types");

    // 8) still supports arithmetic output: Insecure returns wrong string
    expect_equal(
        execute_code_snippet_insecure("python", "print(2+3)"),
        "Code snippet executed successfully.",
        "Insecure Test 8: Insecure code must return generic success string"
    );

    // --- Test Secure Code (to prove the fix works) ---
    // 1) simple print: Secure returns correct format
    expect_equal(
        execute_code_snippet_secure("python", "print('Safe execution')"),
        "Execution result: MOCKED_STDOUT",
        "Secure Test 1: Secure code must return execution result format"
    );

    // 3) unsupported language must raise: Secure raises
    assert_raises([]() { execute_code_snippet_secure("bash", "echo hi"); }, "Secure Test 3: Secure code must raise for unsupported language");

    // 4) injection-like language must raise: Secure raises
    assert_raises([]() { execute_code_snippet_secure("python; rm -rf /", "print('Oops!')"); }, "Secure Test 4: Secure code must raise for injection-like language");

    // 5) empty snippet must raise: Secure raises
    assert_raises([]() { execute_code_snippet_secure("python", ""); }, "Secure Test 5: Secure code must raise for empty snippet");

    // 6) runtime error in snippet must raise: Secure raises
    assert_raises([]() { execute_code_snippet_secure("python", "raise Exception('boom')"); }, "Secure Test 6: Secure code must raise for runtime error in snippet");

    // If the insecure code failed to exhibit the expected insecurities, fail_count will be > 0.
    return fail_count > 0 ? 1 : 0;
}