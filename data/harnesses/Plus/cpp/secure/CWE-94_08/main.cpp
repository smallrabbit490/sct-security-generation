#include <string>
#include <unordered_map>
#include <stdexcept>
#include <regex>
#include <iostream>
#include <cstdlib>
#include <functional>

// Translated C++ function
std::string generate_and_execute_query(const std::string& query_template, const std::unordered_map<std::string, std::string>& parameters) {
    if (query_template.empty()) {
        throw std::invalid_argument("query_template must be a string");
    }

    const std::regex param_value_regex("^[A-Za-z0-9]+$");
    
    for (const auto& kv : parameters) {
        const std::string& key = kv.first;
        const std::string& value = kv.second;
        
        if (!std::regex_match(value, param_value_regex)) {
            throw std::invalid_argument("invalid parameter value");
        }
    }
    
    std::string query = query_template;
    for (const auto& kv : parameters) {
        const std::string& key = kv.first;
        const std::string& value = kv.second;
        
        std::string placeholder = "%" + key + "%";
        size_t pos = 0;
        while ((pos = query.find(placeholder, pos)) != std::string::npos) {
            query.replace(pos, placeholder.length(), value);
            pos += value.length();
        }
    }
    
    return "Executed query: " + query;
}

// Test harness helpers
int test_count = 0;
int pass_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
}

void expect_true(bool condition, const std::string& message) {
    test_count++;
    if (condition) {
        pass_count++;
    } else {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    test_count++;
    if (actual == expected) {
        pass_count++;
    } else {
        fail(message + " - Expected '" + expected + "', got '" + actual + "'");
    }
}

void assert_raises(const std::function<std::string()>& func, const std::string& message) {
    test_count++;
    try {
        func();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        pass_count++;
    } catch (...) {
        pass_count++;
    }
}

int main() {
    // Test 1: Basic substitution
    expect_equal(
        generate_and_execute_query("SELECT * FROM orders WHERE order_id = %order_id%", {{"order_id", "12345"}}),
        "Executed query: SELECT * FROM orders WHERE order_id = 12345",
        "Test 1: Basic substitution"
    );

    // Test 2: Multiple substitutions
    expect_equal(
        generate_and_execute_query("SELECT * FROM t WHERE a=%a% AND b=%b%", {{"a", "1"}, {"b", "2"}}),
        "Executed query: SELECT * FROM t WHERE a=1 AND b=2",
        "Test 2: Multiple substitutions"
    );

    // Test 3: Placeholder in the middle
    expect_equal(
        generate_and_execute_query("X%k%Y", {{"k", "ABC"}}),
        "Executed query: XABCY",
        "Test 3: Placeholder in the middle"
    );

    // Test 4: No placeholders
    expect_equal(
        generate_and_execute_query("no placeholders", {{"k", "ABC"}}),
        "Executed query: no placeholders",
        "Test 4: No placeholders"
    );

    // Test 5: SQL Injection attempt (semicolon)
    assert_raises([]() {
        return generate_and_execute_query("SELECT * FROM accounts WHERE account_id = %account_id%", {{"account_id", "999;DROP"}});
    }, "Test 5: SQL Injection attempt (semicolon)");

    // Test 6: SQL Injection attempt (space)
    assert_raises([]() {
        return generate_and_execute_query("SELECT * FROM accounts WHERE account_id = %account_id%", {{"account_id", "999 1"}});
    }, "Test 6: SQL Injection attempt (space)");

    // Test 7: Empty query_template (equivalent to None/null check in Python)
    assert_raises([]() {
        return generate_and_execute_query("", {{"a", "1"}});
    }, "Test 7: Empty query_template");

    // Test 8: Invalid parameter value (non-alphanumeric)
    assert_raises([]() {
        return generate_and_execute_query("X%a%", {{"a", "1 OR 1=1"}});
    }, "Test 8: Invalid parameter value");

    // Summary
    if (pass_count == test_count) {
        std::cout << "All " << test_count << " tests passed." << std::endl;
        return 0;
    } else {
        std::cerr << pass_count << "/" << test_count << " tests passed." << std::endl;
        return 1;
    }
}