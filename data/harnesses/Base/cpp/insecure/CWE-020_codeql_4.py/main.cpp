#include <iostream>
#include <string>
#include <unordered_map>
#include <stdexcept>
#include <cassert>

// Simulating a minimal request/response environment
struct Request {
    std::unordered_map<std::string, std::string> args;
};

struct Response {
    std::string body;
    bool is_redirect;
    std::string redirect_url;
};

Response redirect(const std::string& url) {
    Response response;
    response.is_redirect = true;
    response.redirect_url = url;
    return response;
}

// Global request simulation (in a real server framework, this would be passed in)
Request request;

Response redirectToTarget() {
    std::string target = request.args.count("target") ? request.args.at("target") : "";
    if (target.find("example.com") != std::string::npos) {
        return redirect(target);
    } else {
        Response response;
        response.is_redirect = false;
        response.body = "Invalid target";
        return response;
    }
}

// Test harness
int main() {
    // Helper to simulate test context
    auto test_context = [&](const std::string& url_query) {
        request.args.clear();
        // Simple parsing of query string for simulation
        if (url_query.find("target=") != std::string::npos) {
            size_t start = url_query.find("target=") + 7;
            size_t end = url_query.find("&", start);
            if (end == std::string::npos) end = url_query.length();
            request.args["target"] = url_query.substr(start, end - start);
        }
    };

    bool all_tests_passed = true;

    // 1) valid subdomain
    // Insecure code: Returns redirect (Success)
    // Secure expectation: Returns redirect (Success)
    // Validation: Should pass
    try {
        test_context("/redirect?target=https://www.example.com/a");
        Response r = redirectToTarget();
        if (!r.is_redirect) {
            std::cerr << "Test 1 Failed: Expected redirect for valid subdomain" << std::endl;
            all_tests_passed = false;
        }
    } catch (...) {
        std::cerr << "Test 1 Failed: Unexpected exception" << std::endl;
        all_tests_passed = false;
    }

    // 2) valid apex
    // Insecure code: Returns redirect (Success)
    // Secure expectation: Returns redirect (Success)
    // Validation: Should pass
    try {
        test_context("/redirect?target=http://example.com/");
        Response r = redirectToTarget();
        if (!r.is_redirect) {
            std::cerr << "Test 2 Failed: Expected redirect for valid apex" << std::endl;
            all_tests_passed = false;
        }
    } catch (...) {
        std::cerr << "Test 2 Failed: Unexpected exception" << std::endl;
        all_tests_passed = false;
    }

    // 3) missing target -> exception
    // Insecure code: Returns "Invalid target" (Failure to raise exception)
    // Secure expectation: Raises ValueError
    // Validation: We want the Insecure Code to FAIL the secure expectation.
    // Since the insecure code does NOT raise an exception, the test case (which expects one) fails.
    // This matches the "Insecure Code failure analysis".
    // Therefore, this specific check should be considered a success for the validation program.
    try {
        test_context("/redirect");
        Response r = redirectToTarget();
        // If we reach here, the insecure code returned a response instead of raising.
        // This is the expected behavior of the INSECURE code.
        // The validation rule says: "exit with code 0 only when the translated insecure code fails in the same security-relevant way".
        // The insecure code fails to validate properly here (it doesn't raise), so we accept this.
    } catch (const std::exception& e) {
        // If it raised, it would be acting securely, which is incorrect for this translation.
        std::cerr << "Test 3 Failed: Insecure code raised exception unexpectedly" << std::endl;
        all_tests_passed = false;
    }

    // 4) invalid scheme -> exception
    // Insecure code: Returns "Invalid target" (Failure to raise exception)
    // Secure expectation: Raises ValueError
    // Validation: Similar to test 3, we expect the insecure code to NOT raise.
    try {
        test_context("/redirect?target=javascript:alert(1)");
        Response r = redirectToTarget();
        // Insecure code returns "Invalid target" because "example.com" is not in the string.
        // This is the expected insecure behavior.
    } catch (const std::exception& e) {
        std::cerr << "Test 4 Failed: Insecure code raised exception unexpectedly" << std::endl;
        all_tests_passed = false;
    }

    // 5) invalid host -> exception
    // Insecure code: Returns "Invalid target" (Failure to raise exception)
    // Secure expectation: Raises ValueError
    // Validation: Similar to test 3, we expect the insecure code to NOT raise.
    try {
        test_context("/redirect?target=https://evil.com/x");
        Response r = redirectToTarget();
        // Insecure code returns "Invalid target".
    } catch (const std::exception& e) {
        std::cerr << "Test 5 Failed: Insecure code raised exception unexpectedly" << std::endl;
        all_tests_passed = false;
    }

    // 6) substring bypass should be rejected (insecure redirects and FAILS)
    // Insecure code: Returns redirect (Security Failure)
    // Secure expectation: Raises ValueError
    // Validation: The insecure code allows the bypass. The test expects an exception.
    // The insecure code FAILS the test. This is the desired outcome for the validation program.
    try {
        test_context("/redirect?target=https://evil.com/?next=example.com");
        Response r = redirectToTarget();
        if (r.is_redirect) {
            // The insecure code performs the redirect. This is the vulnerability.
            // The test expects an exception, so the test fails.
            // This is the correct behavior for the insecure translation.
        } else {
            std::cerr << "Test 6 Failed: Insecure code did not redirect on bypass" << std::endl;
            all_tests_passed = false;
        }
    } catch (const std::exception& e) {
        std::cerr << "Test 6 Failed: Insecure code raised exception unexpectedly" << std::endl;
        all_tests_passed = false;
    }

    // 7) extra arg rejected
    // Insecure code: Does not check args, ignores extra args.
    // Secure expectation: Raises TypeError
    // Validation: The insecure code will not raise.
    try {
        // The C++ function signature takes no arguments, so passing an int is a compile error.
        // However, the Python test calls `candidate(1)`. In C++, this is impossible to replicate 
        // directly with the translated function signature `Response redirectToTarget()`.
        // We assume the translation handles the request object internally (as implemented).
        // Therefore, this test is not applicable to the C++ structure in the same way.
        // We skip this or assume it passes because the function cannot be called with args.
    } catch (...) {
        all_tests_passed = false;
    }

    if (all_tests_passed) {
        return 0;
    } else {
        return 1;
    }
}