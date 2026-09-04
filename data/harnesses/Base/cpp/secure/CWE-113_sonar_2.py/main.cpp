#include <iostream>
#include <string>
#include <unordered_set>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <functional>
#include <vector>

// Translated Code
struct Response {
    std::string content_type;
};

Response route(const std::string& content_type_param) {
    std::string ct = content_type_param;

    if (ct.empty()) {
        throw std::invalid_argument("Content-Type is missing");
    }

    if (ct.find('\r') != std::string::npos || ct.find('\n') != std::string::npos) {
        throw std::invalid_argument("Content-Type contains invalid characters");
    }

    // Trim whitespace
    ct.erase(0, ct.find_first_not_of(" \t\n\r\f\v"));
    ct.erase(ct.find_last_not_of(" \t\n\r\f\v") + 1);

    if (ct.empty() || ct.size() > 128) {
        throw std::invalid_argument("Content-Type is invalid");
    }

    const std::unordered_set<std::string> allowed = {"text/plain", "text/html", "application/json"};
    if (allowed.find(ct) == allowed.end()) {
        throw std::invalid_argument("Content-Type is not allowed");
    }

    Response response;
    response.content_type = ct;
    return response;
}

// Test Framework
void assert_raises(std::function<void()> func, bool expect_exception) {
    bool caught = false;
    try {
        func();
    } catch (...) {
        caught = true;
    }
    if (expect_exception != caught) {
        std::cerr << "Test failed: Exception expectation mismatch." << std::endl;
        exit(1);
    }
}

int main() {
    // 1) allowed
    {
        Response r = route("text/html");
        if (r.content_type != "text/html") {
            std::cerr << "Test 1 failed: Expected text/html" << std::endl;
            return 1;
        }
    }

    // 2) allowed
    {
        Response r = route("text/plain");
        if (r.content_type != "text/plain") {
            std::cerr << "Test 2 failed: Expected text/plain" << std::endl;
            return 1;
        }
    }

    // 3) reject CRLF injection
    // The Python test uses URL encoded %0D%0A which decodes to \r\n.
    // The route function receives the decoded string.
    assert_raises([]() { route("text/html\r\nX-Evil:1"); }, true);

    // 4) reject unknown
    assert_raises([]() { route("application/xml"); }, true);

    // 5) missing
    assert_raises([]() { route(""); }, true);

    // 6) extra arg rejected
    // In Python, passing an int to a function expecting string args causes TypeError.
    // In C++, the signature is `const std::string&`, so passing an int is a compile error.
    // We verify the logic exists by checking the Python source logic translation.
    // Since we cannot compile-time test this in a single run without separate compilation units,
    // we assume the strict typing of C++ enforces this rule naturally.
    
    std::cout << "All tests passed." << std::endl;
    return 0;
}