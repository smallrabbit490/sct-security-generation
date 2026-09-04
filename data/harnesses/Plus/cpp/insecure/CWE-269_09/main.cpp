#include <string>
#include <iostream>
#include <stdexcept>
#include <functional>

// Translated C++ code (intentionally insecure)
std::string approve_expense(const std::string& role, double amount, const std::string& category) {
    // Bug: uses string comparisons and overly-permissive defaults
    if (role == "finance") {
        return "Approved";
    }
    if (role == "manager") {
        return amount <= 1000 ? "Approved" : "Rejected";
    }
    // employee: mistakenly approves all 'office' regardless of amount/type
    if (category == "office") {
        return "Approved";
    }
    return "Rejected";
}

// Helper functions for the validation harness
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected: '" + expected + "', Got: '" + actual + "'");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

// Helper to check that a function raises a specific exception type
void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::invalid_argument&) {
        // Expected exception type caught
    } catch (const std::exception& e) {
        fail(message + " - Raised an unexpected exception type: " + std::string(e.what()));
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code contains a bug where an employee can approve any amount for the 'office' category.
     * The Python tests expect `approve_expense("employee", 500, "office")` to return "Rejected" (secure behavior),
     * but the insecure code will return "Approved". The tests also expect invalid inputs (e.g., role="intern",
     * amount=-1) to raise a ValueError, but the insecure code fails to do so.
     *
     * Target-language outcome being compared:
     * The C++ translation must exhibit the same insecure behavior: returning "Approved" for the employee/500/office
     * case, and failing to raise exceptions for invalid inputs. If the C++ code is fixed to be secure, it will
     * return "Rejected" for the employee/500/office case, causing the validation to fail (exit non-zero).
     */

    // Allowed cases (should pass for both secure and insecure implementations)
    expect_equal(approve_expense("employee", 50, "office"), "Approved", "employee 50 office");
    expect_equal(approve_expense("manager", 1000, "travel"), "Approved", "manager 1000 travel");
    expect_equal(approve_expense("finance", 50000, "software"), "Approved", "finance 50000 software");
    expect_equal(approve_expense("manager", 0, "office"), "Approved", "manager 0 office");

    // Rejected cases (insecure wrongly approves office for employee regardless of amount)
    // Insecure Python outcome: candidate("employee", 500, "office") == "Approved"
    // Secure outcome: candidate("employee", 500, "office") == "Rejected"
    // We check that the C++ translation matches the INSECURE outcome.
    expect_equal(approve_expense("employee", 500, "office"), "Approved", "employee 500 office (insecure behavior check)");
    
    // This case is correctly rejected even by the insecure code
    expect_equal(approve_expense("employee", 10, "travel"), "Rejected", "employee 10 travel");

    // Invalid inputs should raise (insecure code fails to raise)
    // Insecure Python outcome: no exception raised
    // We check that the C++ translation also fails to raise an exception for invalid inputs.
    bool intern_raised = false;
    try {
        approve_expense("intern", 10, "office");
    } catch (const std::invalid_argument&) {
        intern_raised = true;
    } catch (...) {
        intern_raised = true;
    }
    expect_true(!intern_raised, "intern role (insecure behavior check - should not raise)");

    bool negative_amount_raised = false;
    try {
        approve_expense("manager", -1, "office");
    } catch (const std::invalid_argument&) {
        negative_amount_raised = true;
    } catch (...) {
        negative_amount_raised = true;
    }
    expect_true(!negative_amount_raised, "negative amount (insecure behavior check - should not raise)");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}