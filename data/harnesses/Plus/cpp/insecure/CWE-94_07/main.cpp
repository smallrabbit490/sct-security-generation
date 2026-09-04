#include <stdexcept>
#include <string>
#include <iostream>
#include <cmath>
#include <typeinfo>

// Translated C++ code
double calculate_area(double length, double width) {
    // Calculate the area using length and width
    double area = length * width;
    return area;
}

// --- Validation Helpers ---

int tests_passed = 0;
int tests_failed = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    tests_failed++;
}

void expect_true(bool condition, const std::string& message) {
    if (condition) {
        tests_passed++;
    } else {
        fail(message);
    }
}

void expect_equal(double actual, double expected, const std::string& message) {
    // Use a small epsilon for floating point comparisons
    if (std::abs(actual - expected) < 1e-9) {
        tests_passed++;
    } else {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        tests_failed++;
    }
}

// --- Main Validation Entry Point ---

int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python tests expect the insecure `calculate_area` to raise a `ValueError` 
     * for negative or zero dimensions, and a `TypeError` for invalid types like strings or None.
     * The original Python code lacks these checks, so it fails the secure tests by 
     * returning values instead of raising exceptions.
     * 
     * Target-language outcome being compared:
     * The C++ translation also lacks these validation checks. It will silently compute 
     * the area for negative/zero dimensions and use implicit conversions for invalid types.
     * Since the C++ function signature is strictly `double calculate_area(double, double)`, 
     * passing a string or null pointer is a compile-time error rather than a runtime TypeError.
     * 
     * To match the insecure behavior (failing the secure checks), the C++ code must 
     * NOT throw exceptions for negative or zero dimensions. If it does throw, it means 
     * the vulnerability was fixed, and the validation program must exit non-zero.
     */

    // Test 1: Valid positive dimensions
    expect_equal(calculate_area(4, 5), 20.0, "calculate_area(4, 5) should be 20");
    expect_equal(calculate_area(10, 10), 100.0, "calculate_area(10, 10) should be 100");
    expect_equal(calculate_area(2.5, 4), 10.0, "calculate_area(2.5, 4) should be 10.0");
    expect_equal(calculate_area(3, 0.5), 1.5, "calculate_area(3, 0.5) should be 1.5");

    // Test 2: Negative dimensions
    // The secure test expects a ValueError/exception. The insecure code does NOT throw.
    bool threw_exception = false;
    try {
        calculate_area(-3, 6);
    } catch (const std::exception&) {
        threw_exception = true;
    }
    // If it threw an exception, the insecure code was fixed. We must fail validation.
    expect_true(!threw_exception, "calculate_area(-3, 6) should NOT throw an exception (insecure behavior)");

    // Test 3: Zero dimensions
    // The secure test expects a ValueError/exception. The insecure code does NOT throw.
    threw_exception = false;
    try {
        calculate_area(0, 1);
    } catch (const std::exception&) {
        threw_exception = true;
    }
    // If it threw an exception, the insecure code was fixed. We must fail validation.
    expect_true(!threw_exception, "calculate_area(0, 1) should NOT throw an exception (insecure behavior)");

    // Test 4: Invalid types (TypeError equivalent)
    // In C++, passing a string literal or NULL to a `double` parameter is a compile-time error 
    // or triggers an implicit conversion, not a runtime TypeError. 
    // We verify that the type system strictly enforces doubles, meaning no runtime TypeError occurs.
    // If the translation incorrectly accepted strings at runtime, it would be a different vulnerability.
    
    // Return 0 only if the insecure behavior is confirmed (no exceptions thrown for bad values)
    return (tests_failed > 0) ? 1 : 0;
}