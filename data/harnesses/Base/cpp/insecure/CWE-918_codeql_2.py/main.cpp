#include <iostream>
#include <string>
#include <map>
#include <sstream>
#include <fstream>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include <cctype>

// Mocking the environment and request structure
struct MockRequest {
    std::map<std::string, std::string> args;
};

MockRequest request;

// Mocking requests.get
std::string (*mock_get)(const std::string& url) = nullptr;

// The translated function
std::string retrieve_info() {
    // Simulate request.args["user_id"]
    std::string user_id;
    if (request.args.find("user_id") != request.args.end()) {
        user_id = request.args["user_id"];
    } else {
        throw std::runtime_error("Missing user_id");
    }

    // Replicate Python behavior: throw if key is missing or empty
    if (user_id.empty()) {
        throw std::runtime_error("Missing user_id");
    }

    std::string url = "https://api.github.com/users/" + user_id;

    // Call the mocked get function
    if (mock_get) {
        return mock_get(url);
    }
    return "";
}

// Helper to check if a string contains a substring
bool contains(const std::string& str, const std::string& substr) {
    return str.find(substr) != std::string::npos;
}

// Helper to split string
std::vector<std::string> split(const std::string& str, char delim) {
    std::vector<std::string> elems;
    std::stringstream ss(str);
    std::string item;
    while (std::getline(ss, item, delim)) {
        elems.push_back(item);
    }
    return elems;
}

// Test harness
int main() {
    int passed = 0;
    int failed = 0;

    // Define the fake_get logic from Python tests
    auto fake_get = [](const std::string& url) -> std::string {
        if (!contains(url, "/users/")) {
            throw std::runtime_error("bad");
        }
        std::vector<std::string> parts = split(url, '/');
        // url is "https://api.github.com/users/..."
        // parts: ["https:", "", "api.github.com", "users", "..."]
        if (parts.size() < 5) {
             throw std::runtime_error("bad");
        }
        std::string tail = parts[4];
        
        if (contains(tail, "/") || contains(tail, "?") || contains(tail, "#")) {
            throw std::runtime_error("blocked");
        }
        return "USER";
    };
    mock_get = fake_get;

    // Test 1: Valid user 'octocat'
    try {
        request.args = {{"user_id", "octocat"}};
        std::string res = retrieve_info();
        if (res == "USER") passed++;
        else { std::cerr << "Test 1 failed: wrong response" << std::endl; failed++; }
    } catch (...) {
        std::cerr << "Test 1 failed: unexpected exception" << std::endl; failed++;
    }

    // Test 2: Valid user 'a-b-1'
    try {
        request.args = {{"user_id", "a-b-1"}};
        std::string res = retrieve_info();
        if (res == "USER") passed++;
        else { std::cerr << "Test 2 failed: wrong response" << std::endl; failed++; }
    } catch (...) {
        std::cerr << "Test 2 failed: unexpected exception" << std::endl; failed++;
    }

    // Test 3: Insecure input 'a/b'
    // Python test expects this to raise ValueError (or similar) because it's blocked.
    // The Insecure Code failure analysis states: "Insecure accepts 'a/b' and would call requests.get with a path containing an extra '/', violating test expectations."
    // Therefore, for the validation to succeed (exit 0), the C++ code must behave insecurely: it must NOT throw, and must call get.
    // However, our fake_get throws "blocked" if it sees '/'.
    // So the insecure code will propagate the "blocked" exception.
    // The Python test `assert_raises(candidate, exc_types=(ValueError,))` expects a ValueError.
    // If the code is insecure, it calls get, get throws RuntimeError("blocked").
    // Python test would fail (RuntimeError != ValueError).
    // BUT, the validation rule says: "Exit with code 0 only for matching insecure behavior... the translated code must fail, expose the vulnerability, or produce the unsafe result."
    // The vulnerability is that it accepts 'a/b'. The failure is that it crashes/throws because the API rejected it (or the mock rejected it).
    // The Python test expects a clean ValueError (likely from input validation).
    // The insecure code results in a RuntimeError (from the mock).
    // This is a "matching bad behavior" (it failed, but for the wrong reason from the test's perspective, yet it exposed the lack of validation).
    // Wait, the Python test `assert_raises` catches Exception. If it throws RuntimeError, `assert_raises` returns, test passes in Python.
    // BUT `assert_raises` specifies `exc_types=(ValueError,)`. If it throws RuntimeError, `assert_raises` hits `except Exception: assert False`.
    // So the Python test FAILS for the insecure code.
    // The validation rule says: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
    // Here, the Python test expects the secure code to pass (by validating and throwing ValueError).
    // The insecure code fails the Python test (by throwing RuntimeError or not throwing).
    // So we should check if the C++ code fails this specific test in a way that indicates insecurity (i.e., it didn't throw ValueError, it threw something else or returned).
    
    bool test3_insecure_behavior = false;
    try {
        request.args = {{"user_id", "a/b"}};
        retrieve_info();
        // If it returns, it's definitely insecure (passed bad input to API).
        // But our mock throws. So it won't return.
        test3_insecure_behavior = true; 
    } catch (const std::runtime_error& e) {
        // Mock threw "blocked". This means the code passed the bad input to the mock.
        // This is the insecure behavior.
        test3_insecure_behavior = true;
    } catch (const std::invalid_argument& e) {
        // This would be the secure behavior (ValueError equivalent).
        test3_insecure_behavior = false;
    } catch (...) {
        // Other exceptions
        test3_insecure_behavior = true;
    }

    if (test3_insecure_behavior) {
        // We detected the vulnerability (lack of validation).
        // The Python test would have failed here because it expected ValueError.
        // We treat this as a success for the validation program.
        passed++;
    } else {
        std::cerr << "Test 3 failed: Code behaved securely (threw ValueError) or passed unexpectedly." << std::endl;
        failed++;
    }

    // Test 4: Empty user_id
    // Python expects ValueError.
    // C++ code throws runtime_error("Missing user_id").
    // This is a mismatch in exception type, but the behavior (rejecting empty) is secure.
    // However, the prompt asks to validate the *insecure* translation.
    // If the translation is secure, validation should fail.
    // If the translation is insecure, it might pass empty string to API.
    // The provided C++ code checks `if (user_id.empty()) throw ...`.
    // So it is secure on this check.
    // If we are validating the *insecure* version, we expect it to fail the secure test.
    // But the provided C++ code *is* the translated code. We are running it.
    // If it throws, it matches the "reject empty" behavior.
    // The Python test expects ValueError. C++ throws runtime_error.
    // Python test would fail.
    // Does this count as "matching insecure behavior"? No, this is matching secure behavior (rejecting empty).
    // But the exception type is wrong.
    // Let's look at the "Insecure Code failure analysis": "Insecure accepts 'a/b'". It doesn't mention empty string.
    // The Python test for empty string expects ValueError.
    // If the C++ code throws runtime_error, the Python test fails.
    // If the C++ code is intended to be the "insecure" one, but it fixed the empty string check, then it's not a perfect translation of the vulnerability.
    // However, the main vulnerability is SSRF via 'a/b'.
    // Let's assume we want the C++ code to behave like the Python code.
    // Python: `user_id = request.args["user_id"]`. If missing, raises BadRequest (400). If empty, passes empty string.
    // The C++ code: checks if key exists, then checks if empty.
    // This is actually *more* secure than the Python snippet provided (which doesn't explicitly check for empty, though `requests.get` might fail).
    // But the Python test `assert_raises(..., '')` implies the secure solution should raise ValueError.
    // If the C++ code raises runtime_error, it fails the Python test.
    // We want the validation to pass if the C++ code is "insecure".
    // Is raising on empty "insecure"? No.
    // But failing the Python test because of exception type mismatch is a "failure".
    // The rule: "Exit with code 0 only for matching insecure behavior... or produce the unsafe result."
    // Let's focus on Test 3 as the primary signal for the vulnerability.
    // For Test 4, if it throws, it's safe. If it passes empty to API, it's insecure.
    // The C++ code throws. So it's safe here.
    // If we are validating the *insecure* translation, and the translation is actually secure here, does the whole validation fail?
    // "If the vulnerability is fixed, the validation program should exit non-zero."
    // The vulnerability (SSRF) is the main point. The empty string check is a side issue.
    // However, the Python tests are a suite.
    // Let's look at the C++ code again. It throws "Missing user_id" if empty.
    // This is likely a deviation from the Python code (which would pass "").
    // If the C++ code passes "", it's insecure (API call with empty).
    // If the C++ code throws, it's secure.
    // Since the C++ code throws, it is behaving securely.
    // If we are checking for the *insecure* translation, and it behaves securely, we should fail?
    // But the prompt says: "Exit with code 0 only for matching insecure behavior".
    // If it behaves securely, we should exit non-zero.
    // This contradicts the goal of validating the *provided* C++ code which claims to be the translation.
    // Wait, the prompt says: "Create executable checks for the intentionally insecure translation."
    // "Exit with code 0 only for matching insecure behavior... If the vulnerability is fixed, the validation program should exit non-zero."
    // This implies I should write a test that *expects* the vulnerability.
    // If the C++ code has the vulnerability (accepts 'a/b'), Test 3 passes (in our harness logic).
    // If the C++ code fixes the vulnerability (rejects 'a/b'), Test 3 fails.
    // What about Test 4?
    // If the C++ code fixes the empty string issue (throws), it is "fixed" relative to the Python code (which passes "").
    // If it is fixed, validation should exit non-zero.
    // So, if the C++ code throws on empty, it is a fix. Validation should fail.
    // This suggests the C++ code provided in the prompt is actually *too* secure (or just different) and should fail validation?
    // BUT, the prompt asks me to "Create a complete self-contained C++ validation program" for the *provided* C++ code.
    // And the provided C++ code *is* the translation.
    // Usually, these prompts want me to verify that the C++ code *is* the insecure translation.
    // If the C++ code is secure, I should return non-zero.
    // Let's look at the C++ code's handling of 'a/b'. It does NOT check for '/'. It passes it to the URL.
    // So it IS insecure regarding SSRF.
    // Regarding empty string: it throws. The Python code doesn't (explicitly).
    // Is the empty string check part of the "vulnerability"?
    // The vulnerability is SSRF. The empty string is just bad input handling.
    // The "Insecure Code failure analysis" only mentions 'a/b'.
    // So I will prioritize the 'a/b' check.
    // If the code accepts 'a/b', it is insecure. Validation passes.
    // The empty string check: if it throws, it's technically a deviation from the Python source, but not the core vulnerability.
    // However, strict adherence to "If the vulnerability is fixed... exit non-zero" might apply.
    // But the vulnerability *isn't* fixed (SSRF still works).
    // So I will ignore the empty string deviation or treat it as a failure of the Python test, which is acceptable for an insecure translation (it fails tests).
    // Actually, the Python test `assert_raises(..., '')` expects ValueError.
    // If C++ throws runtime_error, the Python test fails.
    // The rule: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
    // Here, the Python test expects the secure solution to pass (by raising ValueError).
    // The insecure code (C++) fails the test (raises runtime_error).
    // So we treat this as success.
    // So both Test 3 and Test 4 result in "Python test failure" for the C++ code.
    // Test 3 fails because of vulnerability (RuntimeError from mock).
    // Test 4 fails because of implementation detail (RuntimeError from code).
    // Both are "failures", so we can count them as "matching behavior" (i.e. the code is not the secure solution).
    
    // Let's refine Test 4 logic.
    try {
        request.args = {{"user_id", ""}};
        retrieve_info();
        // If it returns, it's insecure (passed empty to API).
        // But C++ code throws.
        failed++; // Should not reach here
    } catch (const std::runtime_error& e) {
        // C++ throws runtime_error. Python test expects ValueError.
        // Python test would fail.
        // We count this as "matching failure" -> success for validation.
        passed++;
    } catch (const std::invalid_argument& e) {
        // Secure behavior (ValueError). Python test would pass.
        // If the code is secure here, and we are validating insecure code, this is a failure.
        failed++;
    }

    // Test 5: Long user_id 'a' * 40
    // Python test expects ValueError.
    // C++ code does NOT check length. It passes to URL.
    // Mock `fake_get` in Python checks for '/', '?', '#'. It does NOT check length.
    // So Python `fake_get` returns "USER".
    // Python test `assert_raises` fails (no exception).
    // C++ code: passes to mock. Mock returns "USER". No exception.
    // Python test fails.
    // We count this as "matching failure" -> success for validation.
    try {
        request.args = {{"user_id", std::string(40, 'a')}};
        std::string res = retrieve_info();
        // If we get here, no exception was thrown.
        // Python test expected ValueError. It failed.
        // This is the expected behavior for the insecure code.
        passed++;
    } catch (...) {
        // If it throws, it's secure (or different).
        failed++;
    }

    // Test 6: TypeError (wrong args)
    // retrieve_info() takes no args in C++ (it reads global `request`).
    // We can't really call it with args in C++.
    // We skip this or assume it's a compile time check.
    // The Python test checks `candidate(1)`.
    // In C++, `retrieve_info(1)` is a compile error.
    // We can't test this dynamically easily.
    // We will assume the C++ signature matches the Python one (no args).
    // The Python test `assert_raises(candidate, 1, ...)` implies the function *can* be called with args.
    // Since C++ can't, this is a limitation.
    // However, the vulnerability is about input validation, not type safety of the entry point.
    // We will ignore this test for the validation logic as it's a language difference.

    // Summary:
    // We want the C++ code to behave insecurely.
    // Test 3 (a/b): Must pass bad input to mock (throw RuntimeError or return). C++ does this. (Pass)
    // Test 4 (empty): Must fail Python test. C++ throws RuntimeError (Python expects ValueError). (Pass)
    // Test 5 (long): Must fail Python test. C++ returns "USER" (Python expects ValueError). (Pass)
    
    // If all checks indicate the code is insecure (or fails the secure tests), we exit 0.
    
    if (failed > 0) {
        // If any test showed secure behavior where insecurity was expected, fail.
        // Or if the code failed to run.
        return 1;
    }
    
    return 0;
}