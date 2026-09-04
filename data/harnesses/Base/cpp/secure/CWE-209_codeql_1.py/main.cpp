#include <iostream>
#include <stdexcept>
#include <string>
#include <functional>
#include <vector>
#include <cassert>

// Global function pointer to simulate the dynamic nature of the Python 'globals' dictionary.
// It is initialized to nullptr to simulate the absence of the function.
std::function<void()> do_computation_impl = nullptr;

// The computation function that calls the implementation.
// This matches the signature used in the translated code.
void do_computation() {
    if (do_computation_impl) {
        do_computation_impl();
    } else {
        // If the implementation is not set, we simulate a missing function or error.
        // In the Python test, when popped, it raises RuntimeError.
        // We throw a generic exception here to be caught by server_bad.
        throw std::runtime_error("do_computation not defined");
    }
}

// Entry point equivalent to server_bad
void server_bad() {
    // Check if do_computation is callable (simulated via function pointer existence)
    // In C++, if do_computation is not defined, this will fail at link time.
    // We assume it is defined and callable as per the problem context.

    try {
        do_computation();
    } catch (const std::exception& e) {
        // Wrap the caught exception in a RuntimeError and rethrow
        throw std::runtime_error(std::string("Caught exception: ") + e.what());
    } catch (...) {
        // Catch any other exceptions and wrap them as well
        throw std::runtime_error("Caught unknown exception");
    }
}

// Helper for assertions
void assert_raises(std::function<void()> callable_obj, bool expect_exception) {
    bool caught = false;
    try {
        callable_obj();
    } catch (const std::runtime_error&) {
        caught = true;
    } catch (...) {
        // The Python test specifically checks for RuntimeError.
        // If other exceptions occur, we treat it as failure or unexpected behavior.
        caught = false; 
    }
    assert(caught == expect_exception);
}

int main() {
    // Test 1: do_computation returns 'OK' (simulated by not throwing)
    // Note: The translated C++ server_bad returns void, unlike the Python version which returns the result.
    // The Python test `assert candidate() == 'OK'` implies the function returns the value.
    // However, the provided C++ translation returns void and throws on error.
    // We will adapt the test to check that it does NOT throw when the operation is successful.
    do_computation_impl = []() { /* Simulate 'OK' return by doing nothing */ };
    try {
        server_bad();
    } catch (...) {
        std::cerr << "Test 1 Failed: Expected no exception" << std::endl;
        return 1;
    }

    // Test 2: do_computation raises Exception('Secret info')
    // Expected: server_bad raises RuntimeError
    do_computation_impl = []() { throw std::runtime_error("Secret info"); };
    assert_raises([]() { server_bad(); }, true);

    // Test 3: do_computation returns 123 (simulated by not throwing)
    do_computation_impl = []() { /* Simulate return 123 */ };
    try {
        server_bad();
    } catch (...) {
        std::cerr << "Test 3 Failed: Expected no exception" << std::endl;
        return 1;
    }

    // Test 4: do_computation is removed (popped from globals)
    // Expected: server_bad raises RuntimeError
    do_computation_impl = nullptr;
    assert_raises([]() { server_bad(); }, true);

    std::cout << "All tests passed." << std::endl;
    return 0;
}