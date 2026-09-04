#include <iostream>
#include <string>
#include <thread>
#include <mutex>
#include <chrono>
#include <stdexcept>
#include <typeinfo>
#include <functional>
#include <cassert>

// Define a structure to hold the lock, simulating the thread object in Python
struct ThreadContext {
    std::mutex lock;
};

int getData(int dataStart, int dataLimit, ThreadContext* thread) {
    // Type checks
    // In C++, arguments are statically typed, so we check for negative values here
    // to match the Python logic which checks types and then values.
    if (dataStart < 0 || dataLimit < 0) {
        throw std::runtime_error("ValueError");
    }

    // Thread and lock checks
    if (thread == nullptr) {
        throw std::runtime_error("TypeError");
    }

    if (dataStart > dataLimit) {
        throw std::runtime_error("ValueError");
    }

    // Acquire lock
    thread->lock.lock();
    try {
        dataStart += 1;
    } catch (...) {
        thread->lock.unlock();
        throw;
    }
    thread->lock.unlock();

    // Print thread info
    std::cout << "data from A :: " << dataStart << " Accessor thread :: " << std::this_thread::get_id() << std::endl;

    // Sleep for 0.01 seconds
    std::this_thread::sleep_for(std::chrono::milliseconds(10));

    return dataStart;
}

// Helper for assertion checks
void assert_raises(std::function<void()> callable_obj, const std::string& expected_exception_name) {
    try {
        callable_obj();
        // If no exception was thrown, fail
        std::cerr << "Test failed: Expected exception " << expected_exception_name << " but none was thrown." << std::endl;
        std::exit(1);
    } catch (const std::runtime_error& e) {
        std::string msg = e.what();
        if (msg != expected_exception_name) {
            std::cerr << "Test failed: Expected exception " << expected_exception_name << " but got " << msg << std::endl;
            std::exit(1);
        }
    } catch (...) {
        std::cerr << "Test failed: Expected exception " << expected_exception_name << " but got a different type." << std::endl;
        std::exit(1);
    }
}

int main() {
    // Setup
    ThreadContext t;

    // Test 1: Basic functionality
    int res1 = getData(0, 10, &t);
    if (res1 != 1) {
        std::cerr << "Test failed: Expected 1, got " << res1 << std::endl;
        return 1;
    }

    int res2 = getData(1, 10, &t);
    if (res2 != 2) {
        std::cerr << "Test failed: Expected 2, got " << res2 << std::endl;
        return 1;
    }

    // Test 2: must reject start > limit
    assert_raises([]() { getData(11, 10, nullptr); }, "TypeError"); // nullptr triggers TypeError first
    assert_raises([]() { 
        ThreadContext local_t; 
        getData(11, 10, &local_t); 
    }, "ValueError");

    // Test 3: require shared lock container (nullptr check)
    assert_raises([]() { getData(0, 10, nullptr); }, "TypeError");

    // Test 4: type checks
    // In C++, we cannot pass a string '0' to an int parameter directly.
    // However, the Python test `candidate(0, 10, t, 1)` checks for argument count/type mismatch.
    // Since C++ is statically typed, this is handled at compile time.
    // We simulate the logic check for negative values which corresponds to the ValueError check in Python for types.
    // The Python code raises TypeError for non-ints, but C++ enforces this at compile time.
    // We verify the negative value check which is part of the validation logic.
    assert_raises([]() {
        ThreadContext local_t;
        getData(-1, 10, &local_t);
    }, "ValueError");

    std::cout << "All tests passed." << std::endl;
    return 0;
}