#include <iostream>
#include <string>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <vector>

// Helper function to trim whitespace from both ends of a string
std::string trim(const std::string& str) {
    auto start = str.begin();
    while (start != str.end() && std::isspace(*start)) {
        start++;
    }

    auto end = str.end();
    do {
        end--;
    } while (std::distance(start, end) > 0 && std::isspace(*end));

    return std::string(start, end + 1);
}

// Helper function to check if a string starts with a prefix
bool starts_with(const std::string& str, const std::string& prefix) {
    if (prefix.size() > str.size()) {
        return false;
    }
    return str.compare(0, prefix.size(), prefix) == 0;
}

// Helper function to check if a string contains a substring
bool contains(const std::string& str, char c) {
    return str.find(c) != std::string::npos;
}

std::string http_responser_redirect(const std::string& request_get_target) {
    // In Python, the function takes a request object and accesses request.GET.get('target', '/')
    // In C++, we'll simulate this by passing the target string directly.
    // The Python code checks if request is None or doesn't have 'GET', but in C++ we'll assume
    // the input is a string representing the 'target' parameter from the request.

    // Check if target is a string (in C++, it's always a string in this context)
    // The Python code checks `if not isinstance(target, str): raise TypeError()`
    // In C++, we don't need this check since the parameter is already a string.

    // Trim the target and default to '/' if empty
    std::string target = trim(request_get_target);
    if (target.empty()) {
        target = "/";
    }

    // Check for scheme (e.g., 'http://') or netloc (e.g., 'example.com')
    // urlsplit in Python separates scheme, netloc, path, etc.
    // We'll check for scheme by looking for '://' and netloc by checking if the string
    // starts with something like '//' or contains a domain-like structure.
    if (contains(target, ':') && contains(target, '/') && contains(target, '.')) {
        throw std::invalid_argument("Invalid target: contains scheme or netloc");
    }

    // Ensure the target starts with '/'
    if (!starts_with(target, "/")) {
        throw std::invalid_argument("Invalid target: does not start with '/'");
    }

    return target;
}

// Test harness
int main() {
    int passed = 0;
    int total = 0;

    // Helper macro for assertions
    #define ASSERT_TRUE(cond) \
        total++; \
        if (!(cond)) { \
            std::cerr << "FAIL: Assertion failed at line " << __LINE__ << std::endl; \
        } else { \
            passed++; \
        }

    #define ASSERT_THROW(expr, exc_type) \
        total++; \
        try { \
            expr; \
            std::cerr << "FAIL: Expected exception " << #exc_type << " not thrown at line " << __LINE__ << std::endl; \
        } catch (const exc_type&) { \
            passed++; \
        } catch (const std::exception& e) { \
            std::cerr << "FAIL: Wrong exception type thrown at line " << __LINE__ << ": " << e.what() << std::endl; \
        } catch (...) { \
            std::cerr << "FAIL: Unknown exception thrown at line " << __LINE__ << std::endl; \
        }

    // Test 1: Valid path '/ok'
    ASSERT_TRUE(http_responser_redirect("/ok") == "/ok");

    // Test 2: Valid path '/a/b'
    ASSERT_TRUE(http_responser_redirect("/a/b") == "/a/b");

    // Test 3: Invalid scheme 'https://evil.com'
    // The Python code uses urlsplit. 'https://evil.com' has scheme='https' and netloc='evil.com'.
    // The C++ logic checks for ':', '/', and '.'. 'https://evil.com' contains all three.
    ASSERT_THROW(http_responser_redirect("https://evil.com"), std::invalid_argument);

    // Test 4: Invalid netloc 'evil.com/path'
    // The Python code uses urlsplit. 'evil.com/path' has scheme='', netloc='evil.com'.
    // The C++ logic checks for ':', '/', and '.'. 'evil.com/path' contains '/' and '.', but no ':'.
    // The provided C++ implementation logic is insufficient to catch this specific case 
    // compared to the Python logic, but we must validate the *provided* C++ code.
    // However, looking at the Python tests: assert_raises(candidate, Req('evil.com/path'), exc_types=(ValueError,))
    // The C++ code provided in the prompt:
    // if (contains(target, ':') && contains(target, '/') && contains(target, '.'))
    // 'evil.com/path' -> contains '.' and '/', but not ':'. The condition is false.
    // It proceeds to check starts_with. 'evil.com/path' does not start with '/'. 
    // It throws std::invalid_argument("Invalid target: does not start with '/'").
    // So the test passes (throws exception), though for a slightly different reason than the Python implementation (which fails on netloc).
    // The test requirement is just that it raises an exception.
    ASSERT_THROW(http_responser_redirect("evil.com/path"), std::invalid_argument);

    // Test 5: None request
    // In Python: if request is None ... raise TypeError()
    // In C++, the function signature is std::string http_responser_redirect(const std::string&).
    // We cannot pass None/null to a const std::string& reference without undefined behavior or compilation error.
    // The Python test `assert_raises(candidate, None, ...)` implies the function signature in Python accepts the request object.
    // The C++ translation simplified this to accepting the string directly.
    // Therefore, this specific test regarding the request object being None is not applicable to the C++ function signature.
    // We skip this test as it tests a part of the Python interface (request object validation) that was abstracted away in C++.

    // Test 6: TypeError on wrong arguments
    // In Python: assert_raises(candidate, Req('/ok'), 1, exc_types=(TypeError,))
    // This tests if the function is called with too many arguments.
    // C++ is statically typed. http_responser_redirect(const std::string&) takes exactly one argument.
    // Calling it with two arguments is a compile-time error, not a runtime check.
    // We skip this test as it is enforced by the compiler.

    std::cout << "Tests passed: " << passed << "/" << total << std::endl;

    if (passed == total) {
        return 0;
    } else {
        return 1;
    }
}