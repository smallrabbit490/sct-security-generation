#include <iostream>
#include <string>
#include <stdexcept>
#include <vector>
#include <functional>
#include <cstdlib>

// Translated Code
std::string renderHTML(const std::string& name) {
    // Check if name is empty or exceeds 64 characters
    if (name.empty() || name.size() > 64) {
        throw std::invalid_argument("Invalid name length");
    }

    // Check for carriage return or newline characters
    if (name.find('\r') != std::string::npos || name.find('\n') != std::string::npos) {
        throw std::invalid_argument("Invalid characters in name");
    }

    // HTML escape the name
    std::string safe;
    safe.reserve(name.size() * 2); // Reserve space for potential escaping
    for (char c : name) {
        switch (c) {
            case '&':  safe += "&amp;"; break;
            case '<':  safe += "&lt;"; break;
            case '>':  safe += "&gt;"; break;
            case '"':  safe += "&quot;"; break;
            case '\'': safe += "&#x27;"; break;
            default:   safe += c; break;
        }
    }

    // Construct and return the HTML response
    return "<h1>Hello " + safe + "</h1>";
}

// Test Framework
void assert_raises(const std::function<void()>& func, bool expect_exception) {
    bool caught = false;
    try {
        func();
    } catch (...) {
        caught = true;
    }
    if (expect_exception != caught) {
        std::cerr << "Test failed: Exception expectation mismatch." << std::endl;
        std::exit(1);
    }
}

void check() {
    // 1) normal
    {
        std::string res = renderHTML("Dave");
        if (res.find("Hello Dave") == std::string::npos) {
            std::cerr << "Test 1 failed: 'Hello Dave' not found." << std::endl;
            std::exit(1);
        }
    }

    // 2) XSS must be escaped (insecure would reflect raw and FAIL)
    {
        std::string res = renderHTML("<script>1</script>");
        if (res.find("<script>") != std::string::npos) {
            std::cerr << "Test 2 failed: Raw script tag found." << std::endl;
            std::exit(1);
        }
    }

    // 3) escaped form present
    {
        std::string res = renderHTML("<script>1</script>");
        if (res.find("&lt;script&gt;") == std::string::npos) {
            std::cerr << "Test 3 failed: Escaped script tag not found." << std::endl;
            std::exit(1);
        }
    }

    // 4) missing -> exception
    // Note: The Python test checks for missing query param, which results in None.
    // The C++ signature requires a string. We simulate the "None" case by passing an empty string
    // which triggers the length check (ValueError equivalent).
    {
        assert_raises([]() { renderHTML(""); }, true);
    }

    // 5) empty -> exception
    {
        assert_raises([]() { renderHTML(""); }, true);
    }

    // 6) extra arg rejected
    // Note: C++ is statically typed. Passing an integer to renderHTML(const std::string&)
    // results in a compilation error, which is stricter than a runtime TypeError.
    // We verify the function signature exists and is callable with string.
    // The "extra arg" logic in Python `candidate(1)` is handled by the type system here.
    // We simply verify the function works correctly with valid types.
    {
        // If we could call renderHTML(1), it wouldn't compile.
        // We assume the existence of the function with the correct signature satisfies this
        // constraint in a static context.
    }

    // Additional boundary checks based on implementation
    {
        // Check length > 64
        assert_raises([]() { renderHTML(std::string(65, 'a')); }, true);
        
        // Check newlines
        assert_raises([]() { renderHTML("a\nb"); }, true);
        assert_raises([]() { renderHTML("a\rb"); }, true);
    }
}

int main() {
    try {
        check();
        std::cout << "All tests passed." << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Test suite crashed: " << e.what() << std::endl;
        return 1;
    }
}