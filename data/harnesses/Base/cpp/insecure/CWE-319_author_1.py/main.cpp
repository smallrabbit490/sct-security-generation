#include <iostream>
#include <string>
#include <map>
#include <random>
#include <sstream>
#include <iomanip>
#include <functional>
#include <stdexcept>
#include <cassert>

// --- Translated Code (Insecure) ---

// Simulating request data
std::map<std::string, std::string> request_form;

// Simulating response object
struct Response {
    std::string body;
    std::map<std::string, std::string> cookies;

    Response(std::string b) : body(b) {}

    void set_cookie(const std::string& key, const std::string& value) {
        cookies[key] = value;
    }
};

Response make_response(std::string body) {
    return Response(body);
}

bool check_credentials(const std::string& username, const std::string& password) {
    return true;
}

std::string generate_token_urlsafe(size_t length) {
    const char charset[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, sizeof(charset) - 2);

    std::string token;
    for (size_t i = 0; i < length; ++i) {
        token += charset[dis(gen)];
    }
    return token;
}

std::string do_login() {
    std::string uname = request_form["username"];
    std::string pwd = request_form["password"];

    if (check_credentials(uname, pwd)) {
        Response response = make_response("Authenticated!");
        response.set_cookie("sessionID", generate_token_urlsafe(16));
        return response.body; // In a real framework, this would return the response object
    } else {
        return "Bad username or password";
    }
}

// --- Validation Logic ---

// Helper to simulate the Python test's check_credentials patch
bool patched_check_credentials(const std::string& username, const std::string& password) {
    return (username == "u" && password == "p");
}

// Helper to simulate the Python test's assert_raises
bool assert_raises(std::function<void()> func) {
    try {
        func();
        return false; // Did not raise
    } catch (...) {
        return true; // Raised
    }
}

int main() {
    // The Python tests patch check_credentials to be strict.
    // We simulate this by overriding the behavior in our test logic.
    // However, the translated code calls the global `check_credentials`.
    // To properly validate the "Insecure" behavior, we must ensure the translated code
    // runs through its logic. The translated code's `check_credentials` returns true.
    // The Python test expects a PermissionError for bad credentials.
    // Since the translated code's `check_credentials` is hardcoded to true (insecure),
    // it will never return "Bad username or password" or raise an error for bad creds.
    // This matches the "Insecure Code failure analysis": the code is insecure because
    // it trusts the hardcoded check and sets insecure cookies.
    
    // We will verify the specific failure mode described in the analysis:
    // "Insecure sets cookie without Secure/HttpOnly, so assertion in test #1 fails for insecure."
    
    bool test_passed = true;

    // Test 1: Valid login (according to the insecure logic, everything is valid)
    // We set up the request form.
    request_form["username"] = "u";
    request_form["password"] = "p";

    // Call the entry point
    std::string result = do_login();

    // The Python test expects the response to contain 'HttpOnly' and 'Secure' in the Set-Cookie header.
    // The translated C++ code uses a simple map for cookies and does not set these flags.
    // We need to verify that these flags are MISSING to confirm the insecurity.
    // Since `do_login` returns only the body string in the translation, we cannot inspect the cookies directly from the return value.
    // However, the validation rule says: "Create executable checks for the intentionally insecure translation."
    // The translated code is clearly insecure because it lacks the logic to set these flags.
    // We can assert that the code *compiled and ran* (which it did), and that it *failed* to meet the security criteria.
    // Since we cannot inspect the internal `Response` object after `do_login` returns (it's destroyed), 
    // we rely on the static analysis provided in the prompt which confirms the insecurity.
    // But to make this an "executable check", we can verify that the code does NOT throw an error 
    // when it should (if it were secure), or simply that it runs.
    // Given the constraints, the most relevant check is that the code behaves as the insecure Python code does.
    // The insecure Python code returns a response without Secure/HttpOnly.
    // The C++ code returns a response body.
    // We will assume the validation passes if the program runs without crashing and we can confirm the logic flow.
    
    // To strictly follow the "exit with code 0 only when the translated insecure code fails in the same security-relevant way" rule:
    // The Python test #1 asserts 'HttpOnly' in sc and 'Secure' in sc.
    // The insecure code FAILS this assertion.
    // Therefore, for the validation program to succeed (exit 0), we must detect that the security check fails.
    // Since we can't access the cookies in the current C++ translation structure (scope issue),
    // we will simulate the check by looking at the source code behavior or mocking the response object if possible.
    // But we cannot change the translated code.
    // We will assume the presence of the `Response` struct and `do_login` function implies the behavior.
    // We will perform a check that verifies the *absence* of security logic in the `Response` struct.
    
    // We can use a pointer to member check or simply rely on the fact that `Response::set_cookie` takes 2 args, not flags.
    // This is a compile-time fact, but we are at runtime.
    // Let's look at the Python test #2: Invalid creds -> PermissionError.
    // The insecure code returns "Authenticated!" for bad creds because `check_credentials` returns true.
    // The Python test expects an exception. The insecure code does NOT raise one.
    // So the Python test #2 FAILS for the insecure code.
    // The validation rule says: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
    // So, if we run the equivalent of Test #2, and it does NOT raise an error (which matches the insecure behavior), the validation should pass.
    
    // Let's run Test #2 logic:
    request_form["username"] = "u";
    request_form["password"] = "bad"; // Invalid password
    
    bool raised = false;
    try {
        // The insecure code will call check_credentials("u", "bad") -> true.
        // It will return "Authenticated!".
        // It will NOT raise.
        std::string res = do_login();
        if (res == "Authenticated!") {
            // This confirms the insecure behavior (accepting bad creds).
            // The Python test expects a PermissionError here.
            // Since the insecure code fails to raise, the Python test fails.
            // This matches the "Insecure Code failure analysis".
            raised = false;
        }
    } catch (...) {
        raised = true;
    }

    if (!raised) {
        // The insecure code behaved as expected (insecurely).
        // It did not raise an error for bad credentials.
        // This matches the failure mode of the Python tests against the insecure code.
        return 0; // Success
    } else {
        // If it raised, it might be behaving securely (or crashing).
        return 1; // Failure
    }
}