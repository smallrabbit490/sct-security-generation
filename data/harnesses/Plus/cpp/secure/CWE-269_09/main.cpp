#include <string>
#include <stdexcept>
#include <set>
#include <iostream>
#include <cstdlib>
#include <functional>

// Translated function
std::string approve_expense(const std::string& role, double amount, const std::string& category) {
    if (amount < 0) {
        throw std::invalid_argument("amount must be non-negative");
    }

    const std::set<std::string> roles = {"employee", "manager", "finance"};
    const std::set<std::string> categories = {"travel", "software", "office"};

    if (roles.find(role) == roles.end()) {
        throw std::invalid_argument("invalid role");
    }
    if (categories.find(category) == categories.end()) {
        throw std::invalid_argument("invalid category");
    }

    if (role == "employee") {
        return (category == "office" && amount <= 100.0) ? "Approved" : "Rejected";
    }
    if (role == "manager") {
        return (amount <= 1000.0) ? "Approved" : "Rejected";
    }
    
    // finance
    return "Approved";
}

// Test harness helpers
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: " + expected + ", got: " + actual + ")");
    }
}

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::invalid_argument&) {
        return; // Expected exception type caught
    } catch (const std::exception& e) {
        fail(std::string("Raised an unexpected exception type: ") + e.what());
    }
    fail("Expected an exception but none was raised");
}

int main() {
    // Allowed
    expect_equal(approve_expense("employee", 50, "office"), "Approved", "employee 50 office");
    expect_equal(approve_expense("manager", 1000, "travel"), "Approved", "manager 1000 travel");
    expect_equal(approve_expense("finance", 50000, "software"), "Approved", "finance 50000 software");
    expect_equal(approve_expense("manager", 0, "office"), "Approved", "manager 0 office");

    // Rejected
    expect_equal(approve_expense("employee", 500, "office"), "Rejected", "employee 500 office");
    expect_equal(approve_expense("employee", 10, "travel"), "Rejected", "employee 10 travel");

    // Invalid inputs should raise
    assert_raises([]() { approve_expense("intern", 10, "office"); });
    assert_raises([]() { approve_expense("manager", -1, "office"); });

    std::cout << "All tests passed!" << std::endl;
    return 0;
}