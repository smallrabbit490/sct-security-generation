#include <stdexcept>
#include <string>
#include <iostream>

// Translated C++ code (insecure version)
int reserve_tickets(int age, int num_tickets) {
    int ticket_prices[] = {20, 50, 40};

    double total_cost = 0;

    int ticket_type_index;
    if (age < 12) {
        ticket_type_index = 0;
    } else if (age < 65) {
        ticket_type_index = 1;
    } else {
        ticket_type_index = 2;
    }

    total_cost += ticket_prices[ticket_type_index] * num_tickets;

    // Apply bulk purchase discount
    if (num_tickets >= 5) {
        if (num_tickets >= 10) {
            total_cost *= 0.9;
        } else {
            total_cost *= 0.95;
        }
    }

    return static_cast<int>(total_cost);
}

// Helper functions for validation
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + std::to_string(expected) + 
             ", got " + std::to_string(actual) + ")");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

// Inferred Python insecure outcome:
// For negative age (-5, 3), the insecure Python code computes a total cost of -150 
// (since -5 < 12, price is 20, 20 * 3 = 60, wait, -5 < 12 so price is 20, 20 * 3 = 60... 
// Actually, in Python, -5 < 12 is True, so ticket_type is "Children", price is 20, 20 * 3 = 60).
// Wait, let me recalculate: -5 < 12 -> True -> Children -> 20 * 3 = 60. No discount.
// So the insecure Python code returns 60 for (-5, 3) without raising an exception.
// The secure version must raise a ValueError for negative age.
// For invalid type (30, "2"), the insecure Python code would raise a TypeError when 
// multiplying int by str, but in C++ this wouldn't compile. The C++ version only accepts int.
// The key insecure behavior is: for negative age, the code returns a value (60) instead of raising.
// 
// Target-language outcome being compared:
// The C++ insecure translation should also return 60 for reserve_tickets(-5, 3) without throwing.
// If it throws (secure behavior), the validation should fail (exit non-zero).
// If it returns 60 (matching insecure behavior), the validation should pass (exit 0).

int main() {
    // Normal pricing (no discount)
    expect_equal(reserve_tickets(8, 3), 60, "Normal pricing age=8, num=3");
    expect_equal(reserve_tickets(45, 2), 100, "Normal pricing age=45, num=2");

    // 5% discount boundary
    expect_equal(reserve_tickets(45, 5), 237, "5% discount age=45, num=5");
    expect_equal(reserve_tickets(11, 9), 171, "5% discount age=11, num=9");

    // 10% discount boundary
    expect_equal(reserve_tickets(70, 10), 360, "10% discount age=70, num=10");
    expect_equal(reserve_tickets(70, 12), 432, "10% discount age=70, num=12");

    // Insecure behavior check: negative age
    // The insecure Python code returns 60 for (-5, 3) because -5 < 12 evaluates to True.
    // The C++ insecure translation should also return 60 without throwing.
    // If the vulnerability is fixed, it would throw an exception, and we should exit non-zero.
    bool threw_exception = false;
    int result = 0;
    try {
        result = reserve_tickets(-5, 3);
    } catch (const std::exception&) {
        threw_exception = true;
    } catch (...) {
        threw_exception = true;
    }

    if (threw_exception) {
        // Secure behavior: exception was raised for negative age
        // But we want the insecure behavior to match, so this is a failure
        fail("Insecure behavior mismatch for negative age (expected 60, got exception)");
    } else {
        // Insecure behavior: no exception, check the result matches Python insecure output
        // Python: -5 < 12 -> True -> Children -> 20 * 3 = 60
        expect_equal(result, 60, "Insecure behavior for negative age");
    }

    // All checks passed - insecure behavior matches
    return 0;
}