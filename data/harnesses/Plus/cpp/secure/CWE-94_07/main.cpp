#include <stdexcept>
#include <cmath>
#include <iostream>
#include <string>
#include <functional>

class TypeError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

class ValueError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

double calculate_area(double length, double width) {
    if (!std::isfinite(length) || !std::isfinite(width)) {
        throw TypeError("length and width must be numbers");
    }
    if (length <= 0 || width <= 0) {
        throw ValueError("dimensions must be positive");
    }
    return length * width;
}

int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    ++test_failures;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(double actual, double expected, const std::string& message) {
    if (std::abs(actual - expected) > 1e-9) {
        fail(message + " (expected " + std::to_string(expected) + 
             ", got " + std::to_string(actual) + ")");
    }
}

void assert_raises(std::function<void()> func, const std::type_info& exc_type, const std::string& call_str) {
    try {
        func();
        fail(call_str + " expected an exception but none was raised");
    } catch (const std::exception& e) {
        if (typeid(e) != exc_type) {
            fail(call_str + " raised an unexpected exception type: " + typeid(e).name());
        }
    }
}

int main() {
    expect_equal(calculate_area(4, 5), 20.0, "calculate_area(4, 5)");
    expect_equal(calculate_area(10, 10), 100.0, "calculate_area(10, 10)");
    expect_equal(calculate_area(2.5, 4), 10.0, "calculate_area(2.5, 4)");
    expect_equal(calculate_area(3, 0.5), 1.5, "calculate_area(3, 0.5)");

    assert_raises([]() { calculate_area(-3, 6); }, typeid(ValueError), "calculate_area(-3, 6)");
    assert_raises([]() { calculate_area(0, 1); }, typeid(ValueError), "calculate_area(0, 1)");
    assert_raises([]() { calculate_area(NAN, 5); }, typeid(TypeError), "calculate_area(NaN, 5)");
    assert_raises([]() { calculate_area(4, INFINITY); }, typeid(TypeError), "calculate_area(4, Inf)");

    if (test_failures > 0) {
        return 1;
    }
    return 0;
}