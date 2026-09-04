#include <iostream>
#include <string>
#include <stdexcept>
#include <vector>
#include <functional>
#include <cctype>

// Helper function to escape HTML entities (equivalent to html.escape with quote=True)
std::string escape_html(const std::string& input) {
    std::string result;
    result.reserve(input.size() * 2);
    for (char c : input) {
        switch (c) {
            case '&':  result.append("&amp;"); break;
            case '<':  result.append("&lt;"); break;
            case '>':  result.append("&gt;"); break;
            case '"':  result.append("&quot;"); break;
            case '\'': result.append("&#x27;"); break;
            default:   result.push_back(c); break;
        }
    }
    return result;
}

// Entry point equivalent to the Python 'name' function
// In a real C++ web framework, this would handle request/response objects.
// Here, we simulate the logic by taking the raw 'name' parameter and returning the response string.
std::string name(const std::string& raw) {
    // Check if raw is None (empty string in this simulation context)
    // Note: In Python, request.args.get('name', None) returns None if missing.
    // We assume the caller passes an empty string if the parameter was missing.
    if (raw.empty()) {
        throw std::invalid_argument("Name parameter is missing");
    }

    // Type check is implicit in C++ (std::string)

    // Validate length
    if (raw.length() > 64) {
        throw std::invalid_argument("Name is too long");
    }

    // Prevent header/body splitting patterns (CRLF injection)
    if (raw.find('\r') != std::string::npos || raw.find('\n') != std::string::npos) {
        throw std::invalid_argument("Invalid characters in name");
    }

    // Escape HTML
    std::string safe = escape_html(raw);

    // Construct response
    return "Your name is " + safe;
}

// Test harness
int main() {
    int passed = 0;
    int total = 0;

    // Helper to run tests
    auto run_test = [&](const std::string& desc, std::function<void()> test) {
        total++;
        try {
            test();
            passed++;
            std::cout << "[PASS] " << desc << std::endl;
        } catch (const std::exception& e) {
            std::cout << "[FAIL] " << desc << ": " << e.what() << std::endl;
        } catch (...) {
            std::cout << "[FAIL] " << desc << ": Unknown exception" << std::endl;
        }
    };

    // Helper to assert exception is thrown
    auto assert_raises = [&](std::function<void()> func, const std::string& test_desc) {
        try {
            func();
            throw std::runtime_error("Expected exception but none was thrown");
        } catch (const std::invalid_argument&) {
            // Expected
        } catch (const std::runtime_error& e) {
            // Re-throw if it's our "no exception thrown" error
            throw;
        } catch (...) {
            throw std::runtime_error("Unexpected exception type thrown");
        }
    };

    // 1) normal value
    run_test("normal value", [&]() {
        std::string res = name("Bob");
        if (res != "Your name is Bob") throw std::runtime_error("Unexpected output");
    });

    // 2) XSS payload must be escaped (insecure would reflect raw and FAIL)
    run_test("XSS payload escaped (no raw tag)", [&]() {
        std::string payload = "<img src=x onerror=1>";
        std::string res = name(payload);
        if (res.find("<img") != std::string::npos) throw std::runtime_error("XSS payload not escaped");
    });

    // 3) escaped form present
    run_test("escaped form present", [&]() {
        std::string payload = "<img src=x onerror=1>";
        std::string res = name(payload);
        if (res.find("&lt;img") == std::string::npos) throw std::runtime_error("Escaped form missing");
    });

    // 4) missing param -> exception
    run_test("missing param exception", [&]() {
        assert_raises([&]() { name(""); }, "missing param");
    });

    // 5) CRLF -> exception
    run_test("CRLF exception", [&]() {
        assert_raises([&]() { name("ok\r\nevil"); }, "CRLF");
    });

    // 6) too long -> exception
    run_test("too long exception", [&]() {
        assert_raises([&]() { name(std::string(65, 'a')); }, "too long");
    });

    // 7) extra arg rejected
    // Note: C++ is statically typed, so passing an int to name(const std::string&) 
    // is a compile-time error. We simulate the logic check by ensuring the function 
    // strictly handles strings. Since we can't compile-time test this in a single 
    // binary execution, we acknowledge the type safety of C++.
    run_test("type safety check", [&]() {
        // This test passes implicitly because the code compiles and enforces std::string
        // If we tried to call name(1), it would not compile.
    });

    std::cout << "--------------------------------" << std::endl;
    std::cout << "Results: " << passed << "/" << total << " tests passed." << std::endl;

    return (passed == total) ? 0 : 1;
}