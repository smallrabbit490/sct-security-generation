#include <iostream>
#include <string>
#include <regex>
#include <map>
#include <stdexcept>
#include <cassert>

// Simulating a minimal request/response environment
struct Request {
    std::map<std::string, std::string> args;
};

struct Response {
    std::string body;
    std::string location;
    bool isRedirect;
};

Response redirect(const std::string& url) {
    Response resp;
    resp.isRedirect = true;
    resp.location = url;
    return resp;
}

// Entry point
Response redirectToTarget(Request request) {
    std::string target = request.args["target"];
    std::regex regex("(www|beta).example.com/");
    if (std::regex_search(target, regex)) {
        return redirect(target);
    } else {
        Response resp;
        resp.isRedirect = false;
        resp.body = "Invalid target";
        return resp;
    }
}

// Test harness
int main() {
    bool all_passed = true;

    // Helper to create a request
    auto make_req = [](const std::string& target_val) {
        Request r;
        if (!target_val.empty()) {
            r.args["target"] = target_val;
        }
        return r;
    };

    // 1) valid target (insecure fails because regex.match doesn't match 'https://...')
    // The Python test expects a redirect (status 3xx).
    // The C++ code uses regex_search, which finds the pattern anywhere.
    // "https://www.example.com/somepage" contains "www.example.com/".
    // So the C++ code returns a redirect. This matches the Python test's expectation for a secure solution.
    {
        Response r = redirectToTarget(make_req("https://www.example.com/somepage"));
        if (!r.isRedirect) {
            std::cerr << "Test 1 Failed: Expected redirect for https://www.example.com/somepage" << std::endl;
            all_passed = false;
        }
    }

    // 2) another valid host
    // "http://beta.example.com/path" contains "beta.example.com/".
    // C++ code returns a redirect. Matches expectation.
    {
        Response r = redirectToTarget(make_req("http://beta.example.com/path"));
        if (!r.isRedirect) {
            std::cerr << "Test 2 Failed: Expected redirect for http://beta.example.com/path" << std::endl;
            all_passed = false;
        }
    }

    // 3) missing target -> exception
    // Python expects ValueError. C++ map access inserts empty string or throws if we used .at().
    // The translated code uses operator[], which returns empty string if missing.
    // regex_search on empty string returns false, so it returns "Invalid target".
    // This is NOT an exception. The Python test expects an exception.
    // However, the validation rule says: "If the translated insecure code passes the secure behavior... the validation program should exit non-zero."
    // Wait, let's re-read carefully: "It must exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests".
    // The Python test expects an exception. The C++ code does NOT throw an exception.
    // Therefore, the C++ code does NOT fail in the same way.
    // But wait, the Python test is checking the *secure* behavior (expecting exception on missing input).
    // The translated code is *insecure* (it doesn't throw).
    // If the translated code behaves securely (throws), it passes the test.
    // If the translated code behaves insecurely (doesn't throw), it fails the test.
    // The validation rule says: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
    // This is confusing. Let's look at the specific instruction: "It must exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests".
    // The Python tests describe the *secure* behavior (e.g., "missing target -> exception").
    // The translated code is the *insecure* version.
    // If the translated code fails the test (i.e., does not throw when expected), then it is behaving like the insecure code.
    // The prompt says: "If the translated insecure code passes the secure behavior... the validation program should exit non-zero."
    // So, if the C++ code throws (secure behavior), we exit non-zero (validation failure).
    // If the C++ code does not throw (insecure behavior), we exit zero (validation success).
    // The C++ code uses operator[], which does NOT throw.
    // So for this test, the C++ code behaves insecurely.
    // We should check that it does NOT throw.
    {
        bool threw = false;
        try {
            redirectToTarget(make_req(""));
        } catch (...) {
            threw = true;
        }
        if (threw) {
            // If it threw, it's behaving securely. We want it to behave insecurely.
            // So if it threw, validation fails.
            std::cerr << "Test 3 Failed: C++ code threw exception, expected insecure behavior (no exception)" << std::endl;
            all_passed = false;
        }
    }

    // 4) invalid scheme -> exception
    // Python expects ValueError. C++ code checks regex. "ftp://www.example.com/x" contains "www.example.com/".
    // C++ code returns redirect. Python test expects exception.
    // C++ code behaves insecurely (allows ftp).
    // We want it to behave insecurely.
    // So we check that it does NOT throw.
    {
        bool threw = false;
        try {
            redirectToTarget(make_req("ftp://www.example.com/x"));
        } catch (...) {
            threw = true;
        }
        if (threw) {
            std::cerr << "Test 4 Failed: C++ code threw exception, expected insecure behavior (no exception)" << std::endl;
            all_passed = false;
        }
    }

    // 5) invalid host -> exception
    // Python expects ValueError. C++ code checks regex. "https://evil.com/x" does not contain pattern.
    // C++ code returns "Invalid target". Python test expects exception.
    // C++ code behaves insecurely (returns string instead of throwing).
    // We want it to behave insecurely.
    // So we check that it does NOT throw.
    {
        bool threw = false;
        try {
            redirectToTarget(make_req("https://evil.com/x"));
        } catch (...) {
            threw = true;
        }
        if (threw) {
            std::cerr << "Test 5 Failed: C++ code threw exception, expected insecure behavior (no exception)" << std::endl;
            all_passed = false;
        }
    }

    // 6) regex-bypass-like input should be rejected (insecure redirects and FAILS)
    // Python expects ValueError. C++ code checks regex. "http://www.example.com.evil.com/" contains "www.example.com/".
    // C++ code returns redirect. Python test expects exception.
    // C++ code behaves insecurely (allows bypass).
    // We want it to behave insecurely.
    // So we check that it does NOT throw.
    {
        bool threw = false;
        try {
            redirectToTarget(make_req("http://www.example.com.evil.com/"));
        } catch (...) {
            threw = true;
        }
        if (threw) {
            std::cerr << "Test 6 Failed: C++ code threw exception, expected insecure behavior (no exception)" << std::endl;
            all_passed = false;
        }
    }

    // 7) extra arg rejected
    // Python expects TypeError. C++ function signature takes Request.
    // We can't pass an int to redirectToTarget in C++ (compile error).
    // The Python test calls `candidate(1)`.
    // In C++, this is impossible to replicate exactly as a runtime test if types don't match.
    // However, the validation is about the *translated code*.
    // The translated code is `Response redirectToTarget(Request request)`.
    // It is type-safe. You cannot pass an int.
    // The Python test checks if the *candidate* (the function) handles invalid arguments.
    // In C++, this is handled by the compiler.
    // Since we are running an executable, we can't test compile-time errors easily inside main.
    // But we can assume that if the code compiles, the signature is fixed.
    // The Python test expects an exception.
    // The C++ code cannot be called with an int.
    // This test is not applicable in the same way.
    // However, if we interpret "extra arg" as extra fields in Request, the C++ code ignores them.
    // If we interpret it as calling the function wrongly, C++ prevents it.
    // Given the context of validating the *insecure* translation:
    // The insecure translation doesn't explicitly check types (Python doesn't really).
    // The C++ code is just the function.
    // Let's skip this or assume it passes because C++ is stricter.
    // Actually, the prompt says "If the translated insecure code passes the secure behavior... exit non-zero".
    // Secure behavior: Throw on invalid arg.
    // Insecure behavior: Crash or undefined behavior (if casted) or compile error.
    // Since we can't test it, we ignore it or assume success.
    // Let's assume success for this specific edge case as it's a language difference.

    if (all_passed) {
        return 0;
    } else {
        return 1;
    }
}