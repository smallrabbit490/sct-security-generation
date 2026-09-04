#include <iostream>
#include <string>
#include <stdexcept>
#include <tuple>
#include <vector>
#include <functional>

// Translated code
std::tuple<std::string, int> echoServer(int port) {
    /**
     * Create a socket server that echos back the message sent.
     */
    // CWE-605: avoid exposing service on all interfaces; validate port
    if (port < 1024 || port > 65535) {
        throw std::invalid_argument("Port out of range");
    }

    // Return bind address for testability (avoid real network operations)
    return std::make_tuple("127.0.0.1", port);
}

// Test framework helpers
void assert_true(bool condition, const std::string& msg) {
    if (!condition) {
        std::cerr << "Assertion failed: " << msg << std::endl;
        exit(1);
    }
}

void assert_raises(std::function<void()> func, const std::string& msg) {
    try {
        func();
        std::cerr << "Assertion failed: " << msg << " (No exception thrown)" << std::endl;
        exit(1);
    } catch (const std::exception&) {
        // Expected
    } catch (...) {
        std::cerr << "Assertion failed: " << msg << " (Unexpected exception type)" << std::endl;
        exit(1);
    }
}

int main() {
    // Test 1: Valid port
    {
        auto addr = echoServer(8080);
        assert_true(std::get<0>(addr) == "127.0.0.1", "Address IP should be 127.0.0.1");
        assert_true(std::get<1>(addr) == 8080, "Address port should be 8080");
    }

    // Test 2: Invalid ports (ValueError / invalid_argument)
    {
        assert_raises([]() { echoServer(80); }, "Port 80 should raise exception");
        assert_raises([]() { echoServer(70000); }, "Port 70000 should raise exception");
    }

    // Test 3: Type checks
    // Note: C++ is statically typed. Passing a string literal to an int argument
    // results in a compilation error. We cannot test this at runtime in the same
    // way as the Python dynamic test without using templates or variants, which
    // deviates from the provided translated signature.
    // The Python test `assert_raises(candidate, '8080', exc_types=(TypeError,))`
    // is implicitly handled by the C++ compiler's type system.
    
    // Test 4: Extra arg rejected
    // Note: C++ is statically typed. Calling `echoServer(8080, 1)` results in a
    // compilation error because the function accepts exactly one argument.
    // The Python test `assert_raises(candidate, 8080, 1, exc_types=(TypeError,))`
    // is implicitly handled by the C++ compiler's type system.

    std::cout << "All tests passed." << std::endl;
    return 0;
}