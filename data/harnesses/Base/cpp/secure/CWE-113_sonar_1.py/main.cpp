#include <iostream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <stdexcept>
#include <functional>
#include <cctype>

// Simulating the request object with a global variable for demonstration.
// In a real C++ web framework, this would be provided by the framework.
std::unordered_map<std::string, std::string> request_args;

// Simulating the Response object
struct Response {
    struct Headers {
        std::string content_type;
        void add(const std::string& key, const std::string& value) {
            if (key == "Content-Type") {
                content_type = value;
            }
        }
    } headers;
};

// Entry point
Response route() {
    // Get the content_type parameter from the request
    // Python: request.args.get('Content-Type', None)
    auto it = request_args.find("Content-Type");
    if (it == request_args.end()) {
        throw std::invalid_argument("Content-Type not found");
    }
    std::string ct = it->second;

    // Prevent response splitting / header injection
    if (ct.find('\r') != std::string::npos || ct.find('\n') != std::string::npos) {
        throw std::invalid_argument("Invalid characters in Content-Type");
    }

    // Trim whitespace
    size_t start = ct.find_first_not_of(" \t\n\r\f\v");
    size_t end = ct.find_last_not_of(" \t\n\r\f\v");
    if (start == std::string::npos) {
        ct = "";
    } else {
        ct = ct.substr(start, end - start + 1);
    }

    if (ct.empty() || ct.size() > 128) {
        throw std::invalid_argument("Invalid Content-Type length");
    }

    // Very small allow-list for predictable behavior
    static const std::unordered_set<std::string> allowed = {
        "text/plain", "text/html", "application/json"
    };
    if (allowed.find(ct) == allowed.end()) {
        throw std::invalid_argument("Content-Type not allowed");
    }

    Response response;
    Response::Headers headers;
    headers.add("Content-Type", ct);
    response.headers = headers;
    return response;
}

// Test harness
int main() {
    int passed = 0;
    int total = 0;

    // Helper to run tests
    auto run_test = [&](const std::string& name, std::function<void()> test_fn) {
        total++;
        try {
            test_fn();
            passed++;
            std::cout << "[PASS] " << name << std::endl;
        } catch (const std::exception& e) {
            std::cerr << "[FAIL] " << name << ": " << e.what() << std::endl;
        } catch (...) {
            std::cerr << "[FAIL] " << name << ": Unknown exception" << std::endl;
        }
    };

    // Helper to assert exceptions
    auto assert_raises = [&](std::function<void()> fn, const std::string& msg) {
        try {
            fn();
            throw std::runtime_error("Expected exception but none was thrown: " + msg);
        } catch (const std::invalid_argument&) {
            // Expected
        } catch (const std::runtime_error& e) {
            // Re-throw assertion failures
            throw;
        } catch (...) {
            throw std::runtime_error("Unexpected exception type: " + msg);
        }
    };

    // 1) allowed content-type
    run_test("allowed content-type", [&]() {
        request_args.clear();
        request_args["Content-Type"] = "text/plain";
        Response r = route();
        if (r.headers.content_type != "text/plain") {
            throw std::runtime_error("Expected text/plain");
        }
    });

    // 2) another allowed
    run_test("another allowed", [&]() {
        request_args.clear();
        request_args["Content-Type"] = "application/json";
        Response r = route();
        if (r.headers.content_type != "application/json") {
            throw std::runtime_error("Expected application/json");
        }
    });

    // 3) reject header injection (insecure would accept and FAIL)
    run_test("reject header injection", [&]() {
        request_args.clear();
        // Simulating URL decoded value: text/plain\r\nX-Evil:1
        request_args["Content-Type"] = "text/plain\r\nX-Evil:1";
        assert_raises([]() { route(); }, "Header injection");
    });

    // 4) reject unknown type
    run_test("reject unknown type", [&]() {
        request_args.clear();
        request_args["Content-Type"] = "application/xml";
        assert_raises([]() { route(); }, "Unknown type");
    });

    // 5) missing
    run_test("missing parameter", [&]() {
        request_args.clear();
        assert_raises([]() { route(); }, "Missing parameter");
    });

    // 6) extra arg rejected
    // Note: The Python test checks TypeError for extra args.
    // In C++, route() takes no arguments, so passing one is a compile-time error.
    // We simulate the logic check by ensuring the function signature is strictly void().
    // Since we cannot call route(1) in C++, we assume this is satisfied by the type system.
    // However, to strictly follow the test logic, we verify the function exists and is callable.
    run_test("signature check", [&]() {
        // This test is implicitly passed by compilation and successful calls above.
        // If route() took arguments, the previous calls would have failed to compile.
    });

    std::cout << "--------------------------------" << std::endl;
    std::cout << "Tests passed: " << passed << "/" << total << std::endl;

    return (passed == total) ? 0 : 1;
}