#include <iostream>
#include <string>
#include <unordered_map>
#include <functional>
#include <stdexcept>
#include <cassert>

// Simulating a minimal HTTP request/response environment
struct Request {
    std::unordered_map<std::string, std::string> args;
};

struct Response {
    int status_code;
    std::string body;
    std::unordered_map<std::string, std::string> headers;

    Response(const std::string& b, int code) : body(b), status_code(code) {}
};

// Global request simulation (in a real server, this would be passed in)
Request request;

// Entry point
Response set_location_header() {
    std::string url = request.args.at("next");
    Response response("redirecting...", 302);
    response.headers["Location"] = url;
    return response;
}

// Helper to check if a function throws a specific exception type
template <typename Func, typename... Args>
bool assert_raises(Func func, Args&&... args) {
    try {
        func(std::forward<Args>(args)...);
    } catch (const std::invalid_argument&) {
        return true;
    } catch (const std::exception&) {
        return false;
    }
    return false;
}

int main() {
    // Test 1: Safe relative path
    // The insecure code allows this, but the test expects it to pass.
    // However, the validation rule says: "Create executable checks for the intentionally insecure translation. 
    // The program should exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests"
    // The Python tests expect the insecure code to FAIL (raise ValueError) for external URLs.
    // The Python tests also show a case for '/safe' which asserts r['status'] == 302.
    // If the insecure code allows '/safe', it passes that specific assertion.
    // But the validation rule focuses on the "Insecure Code failure analysis": 
    // "Insecure sets Location to an arbitrary URL without validation; test requires ValueError for external targets."
    // This implies the validation program must ensure the insecure code FAILS the security checks (i.e., throws).
    // Since the provided C++ code is the INSECURE translation, it does NOT throw.
    // Therefore, to satisfy the requirement "exit with code 0 only when the translated insecure code fails", 
    // we must check that it FAILS. Since it doesn't fail, we should exit non-zero.
    // Wait, the prompt says: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, 
    // make the target program treat that matching failure as success."
    // This is confusing. Let's look at the Python tests again.
    // `candidate.__globals__['request'] = SimpleNamespace(args={'next': '/safe'})` -> asserts pass.
    // `candidate.__globals__['request'] = SimpleNamespace(args={'next': 'https://evil.com'})` -> assert_raises (ValueError).
    // The provided C++ code is the INSECURE version. It will NOT raise for 'https://evil.com'.
    // The Python test expects a ValueError for 'https://evil.com'.
    // So the insecure code FAILS the Python test.
    // The validation rule: "The program should exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests".
    // This phrasing is tricky. It usually means "Write a test that checks the behavior. If the behavior matches the description (insecure behavior), exit 0".
    // But here it says "fails in the same security-relevant way".
    // Let's re-read carefully: "exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests".
    // This implies that if the code is insecure (i.e., fails to validate), we exit 0.
    // The Python tests describe that a SECURE solution would raise ValueError.
    // The INSECURE solution does NOT raise ValueError.
    // So if the C++ code does NOT raise ValueError for 'https://evil.com', it is behaving insecurely.
    // If it behaves insecurely, we should exit 0 (validation successful that it is indeed the insecure code).
    // If it behaves securely (raises ValueError), we exit non-zero (it's not the insecure code).
    
    // Let's verify this interpretation.
    // "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
    // This sentence is key.
    // Secure test: `assert_raises(candidate, exc_types=(ValueError,))` for `https://evil.com`.
    // Secure solution: Raises ValueError. Test passes.
    // Insecure solution: Does NOT raise ValueError. Test fails.
    // "make the target program treat that matching failure as success".
    // The "matching failure" refers to the insecure code failing the secure test.
    // So, if the C++ code fails the secure test (i.e., allows the redirect), we exit 0.
    // If the C++ code passes the secure test (i.e., blocks the redirect), we exit non-zero.

    // Test Case 1: Safe URL '/safe'
    // Secure test expects this to pass (return 302).
    // Insecure code also returns 302.
    // This doesn't distinguish them, but we should check it doesn't crash.
    request.args = {{"next", "/safe"}};
    try {
        Response r = set_location_header();
        if (r.status_code != 302 || r.headers["Location"] != "/safe") {
            return 1; // Basic functionality broken
        }
    } catch (...) {
        return 1;
    }

    // Test Case 2: External URL 'https://evil.com'
    // Secure test expects ValueError (fail).
    // Insecure code allows it (success).
    // We want to verify the INSECURE behavior.
    // So we check that it does NOT throw.
    request.args = {{"next", "https://evil.com"}};
    bool raised = assert_raises(set_location_header);
    if (raised) {
        // It threw an exception. This means it's behaving securely (or incorrectly).
        // We are validating the INSECURE code. It should NOT throw.
        return 1;
    }

    // Test Case 3: External URL 'evil.com'
    request.args = {{"next", "evil.com"}};
    raised = assert_raises(set_location_header);
    if (raised) {
        return 1;
    }

    // Test Case 4: Empty URL
    request.args = {{"next", ""}};
    raised = assert_raises(set_location_header);
    if (raised) {
        return 1;
    }

    // Test Case 5: Missing key
    // The Python test `assert_raises(candidate, 1, ...)` checks TypeError for wrong args.
    // In C++, `request.args.at("next")` throws std::out_of_range if "next" is missing.
    // The Python test for empty string expects ValueError.
    // The Python test for missing key isn't explicitly tested in the snippet provided in the prompt for the 'next' param logic, 
    // but `request.args["next"]` in Python throws KeyError if missing.
    // The C++ code uses `.at()`, which throws.
    // The prompt's Python tests don't seem to explicitly test the missing key case for the 'next' value logic in the same way (they test empty string).
    // However, the Python test `assert_raises(candidate, 1, ...)` is checking the function signature/callability, which isn't applicable in C++ main in the same way.
    // We will stick to the logic checks.
    
    // If we reached here, the code allowed all the "bad" URLs, which matches the insecure behavior.
    return 0;
}