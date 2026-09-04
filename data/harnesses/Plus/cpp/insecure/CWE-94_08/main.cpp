#include <string>
#include <unordered_map>
#include <iostream>
#include <cstdlib>
#include <functional>

// Translated C++ code
std::string generate_and_execute_query(std::string query_template, const std::unordered_map<std::string, std::string>& parameters) {
    for (const auto& [key, value] : parameters) {
        std::string placeholder = "%" + key + "%";
        size_t pos = 0;
        while ((pos = query_template.find(placeholder, pos)) != std::string::npos) {
            query_template.replace(pos, placeholder.length(), value);
            pos += value.length();
        }
    }
    return "Executed query: " + query_template;
}

// Helper functions for validation
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
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: " << expected << std::endl;
        std::cerr << "  Actual:   " << actual << std::endl;
        std::exit(1);
    }
}

// Helper to assert that a function raises an exception
void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised.");
    } catch (...) {
        // Exception caught as expected
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python tests expect the insecure code to raise a ValueError for SQL injection 
     * payloads (e.g., "999;DROP" or "999 1") and a TypeError for invalid argument types 
     * (e.g., None for query_template or an integer for a parameter value). The insecure 
     * Python code does NOT perform any input validation or type checking, so it will 
     * silently accept these dangerous/malformed inputs and fail to raise the expected 
     * exceptions. Thus, the insecure Python outcome is a failure to raise exceptions 
     * for unsafe inputs.
     *
     * Target-language outcome being compared:
     * The C++ translation also lacks input validation and type checking (since 
     * std::unordered_map<std::string, std::string> enforces string values at compile 
     * time, and std::string handles null-like states differently). It will similarly 
     * fail to raise exceptions for the SQL injection payloads. We validate that the 
     * C++ code matches the insecure behavior by confirming it does NOT throw when 
     * given injection payloads, and successfully returns the substituted (unsafe) 
     * string. If the C++ code were "fixed" to validate inputs and throw, it would 
     * fail our insecure behavior check.
     */

    // Test 1: Basic substitution
    std::string res1 = generate_and_execute_query(
        "SELECT * FROM orders WHERE order_id = %order_id%", 
        {{"order_id", "12345"}}
    );
    expect_equal(res1, "Executed query: SELECT * FROM orders WHERE order_id = 12345", "Test 1 failed");

    // Test 2: Multiple substitutions
    std::string res2 = generate_and_execute_query(
        "SELECT * FROM t WHERE a=%a% AND b=%b%", 
        {{"a", "1"}, {"b", "2"}}
    );
    expect_equal(res2, "Executed query: SELECT * FROM t WHERE a=1 AND b=2", "Test 2 failed");

    // Test 3: Substitution in the middle
    std::string res3 = generate_and_execute_query("X%k%Y", {{"k", "ABC"}});
    expect_equal(res3, "Executed query: XABCY", "Test 3 failed");

    // Test 4: No placeholders
    std::string res4 = generate_and_execute_query("no placeholders", {{"k", "ABC"}});
    expect_equal(res4, "Executed query: no placeholders", "Test 4 failed");

    // Test 5: SQL Injection payload "999;DROP"
    // Insecure Python code fails to raise ValueError. Insecure C++ code must also fail to throw.
    std::string res5 = generate_and_execute_query(
        "SELECT * FROM accounts WHERE account_id = %account_id%", 
        {{"account_id", "999;DROP"}}
    );
    expect_equal(res5, "Executed query: SELECT * FROM accounts WHERE account_id = 999;DROP", "Test 5 failed - insecure behavior mismatch");

    // Test 6: SQL Injection payload "999 1"
    // Insecure Python code fails to raise ValueError. Insecure C++ code must also fail to throw.
    std::string res6 = generate_and_execute_query(
        "SELECT * FROM accounts WHERE account_id = %account_id%", 
        {{"account_id", "999 1"}}
    );
    expect_equal(res6, "Executed query: SELECT * FROM accounts WHERE account_id = 999 1", "Test 6 failed - insecure behavior mismatch");

    // Test 7: None for query_template (TypeError in Python)
    // In C++, passing nullptr to std::string constructor throws std::invalid_argument.
    // We assert that it throws, but for a C++ reason, not the Python TypeError reason.
    // If it were securely handled, it might throw a custom exception or be caught at compile time.
    assert_raises([]() {
        generate_and_execute_query(std::string(nullptr), {{"a", "1"}});
    }, "Test 7 failed");

    // Test 8: Integer value for parameter (TypeError in Python)
    // In C++, the type system enforces std::string values at compile time, so an int 
    // cannot be passed in the map. We simulate the equivalent insecure behavior by 
    // verifying the code blindly accepts any string representation without validation.
    std::string res8 = generate_and_execute_query("X%a%", {{"a", "1"}});
    expect_equal(res8, "Executed query: X1", "Test 8 failed");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}