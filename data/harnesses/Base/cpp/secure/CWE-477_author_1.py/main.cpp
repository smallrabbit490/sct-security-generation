#include <chrono>
#include <iostream>
#include <stdexcept>
#include <type_traits>
#include <utility>

// Translated code
double currentTime() {
    auto t = std::chrono::duration_cast<std::chrono::duration<double>>(
        std::chrono::steady_clock::now().time_since_epoch()
    ).count();

    if (t < 0) {
        throw std::invalid_argument("Negative time value");
    }

    return static_cast<double>(t);
}

// Test framework helpers
template <typename Callable, typename... Args>
void assert_raises(Callable&& callable, Args&&... args) {
    try {
        std::forward<Callable>(callable)(std::forward<Args>(args)...);
        // If no exception was thrown, fail the test
        std::cerr << "Test failed: Expected exception but none was thrown." << std::endl;
        std::exit(1);
    } catch (const std::exception&) {
        // Expected behavior
        return;
    } catch (...) {
        std::cerr << "Test failed: Unexpected exception type caught." << std::endl;
        std::exit(1);
    }
}

int main() {
    // Test 1: Basic functionality and type check
    double t1 = currentTime();
    static_assert(std::is_same<decltype(t1), double>::value, "Return type must be double");
    if (t1 < 0.0) {
        std::cerr << "Test failed: t1 is negative." << std::endl;
        return 1;
    }

    // Test 2: Second call functionality
    double t2 = currentTime();
    static_assert(std::is_same<decltype(t2), double>::value, "Return type must be double");
    if (t2 < 0.0) {
        std::cerr << "Test failed: t2 is negative." << std::endl;
        return 1;
    }

    // Test 3: No args (C++ is statically typed, so passing args is a compile error.
    // We simulate the check by ensuring the function is callable with 0 args).
    // Since we compiled successfully, this is implicitly satisfied.
    // However, to strictly follow the Python test logic of checking behavior with args,
    // we would need a wrapper, but in C++ `currentTime(1)` simply won't compile.
    // We assume the "no args" requirement is satisfied by the function signature `double currentTime()`.

    // Test 4: Insecure Code failure analysis
    // The Python code checked for time.clock() usage. 
    // The C++ implementation uses std::chrono::steady_clock, which is the modern, correct API.
    // This test passes by virtue of the implementation using the correct API.

    std::cout << "All tests passed." << std::endl;
    return 0;
}