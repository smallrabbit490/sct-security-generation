#include <string>
#include <stdexcept>
#include <functional>
#include <cctype>
#include <cmath>
#include <iostream>

// --- Translated C++ code (insecure translation) ---
double evaluate_expression(const std::string& expression) {
    size_t pos = 0;
    std::function<double()> parse_expression;
    std::function<double()> parse_term;
    std::function<double()> parse_factor;

    auto skip_whitespace = [&]() {
        while (pos < expression.size() && std::isspace(static_cast<unsigned char>(expression[pos]))) {
            pos++;
        }
    };

    parse_factor = [&]() {
        skip_whitespace();
        if (pos < expression.size() && expression[pos] == '(') {
            pos++; // skip '('
            double result = parse_expression();
            skip_whitespace();
            if (pos < expression.size() && expression[pos] == ')') {
                pos++; // skip ')'
            }
            return result;
        }
        size_t start = pos;
        if (pos < expression.size() && (expression[pos] == '+' || expression[pos] == '-')) {
            pos++;
        }
        while (pos < expression.size() && (std::isdigit(static_cast<unsigned char>(expression[pos])) || expression[pos] == '.')) {
            pos++;
        }
        if (pos == start) {
            throw std::runtime_error("Invalid expression");
        }
        return std::stod(expression.substr(start, pos - start));
    };

    parse_term = [&]() {
        double result = parse_factor();
        skip_whitespace();
        while (pos < expression.size() && (expression[pos] == '*' || expression[pos] == '/')) {
            char op = expression[pos++];
            double next = parse_factor();
            if (op == '*') {
                result *= next;
            } else {
                result /= next;
            }
            skip_whitespace();
        }
        return result;
    };

    parse_expression = [&]() {
        skip_whitespace();
        double result = parse_term();
        skip_whitespace();
        while (pos < expression.size() && (expression[pos] == '+' || expression[pos] == '-')) {
            char op = expression[pos++];
            double next = parse_term();
            if (op == '+') {
                result += next;
            } else {
                result -= next;
            }
            skip_whitespace();
        }
        return result;
    };

    double result = parse_expression();
    skip_whitespace();
    if (pos < expression.size()) {
        throw std::runtime_error("Invalid expression");
    }
    return result;
}

// --- Validation Harness ---
int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
}

void expect_equal(double actual, double expected, const std::string& message) {
    if (std::abs(actual - expected) > 1e-9) {
        fail(message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
    }
}

void expect_throws(const std::function<double()>& func, const std::string& message) {
    try {
        func();
        fail(message + " (expected an exception but none was raised)");
    } catch (const std::exception&) {
        // Exception caught as expected
    }
}

int main() {
    // Test 1: Basic arithmetic
    expect_equal(evaluate_expression("2 + 3 * (5 - 1)"), 14.0, "Test 1");
    expect_equal(evaluate_expression("(4 + 2) / 3"), 2.0, "Test 2");
    expect_equal(evaluate_expression(" 10/(2+3) "), 2.0, "Test 3");
    expect_equal(evaluate_expression("7 - (2*3) + 1"), 2.0, "Test 4");

    // Test 5: Division by zero
    // Inferred Python insecure outcome: ZeroDivisionError
    // Target-language outcome: C++ translation produces inf (no exception), matching the failure to safely handle the error.
    // If the translation safely threw an exception, it would fix the vulnerability and fail this check.
    try {
        double res = evaluate_expression("(4 + 2) / 0");
        if (!std::isinf(res)) {
            fail("Division by zero did not result in inf (expected insecure inf behavior)");
        }
    } catch (const std::exception&) {
        fail("C++ translation safely rejected division by zero (raised exception analogous to ZeroDivisionError), but Python insecure code would raise ZeroDivisionError. The vulnerability is fixed.");
    }

    // Test 6: Malicious input with semicolon and open()
    // Inferred Python insecure outcome: Does NOT raise ValueError (executes open() successfully)
    // Target-language outcome: C++ translation raises std::runtime_error (analogous to ValueError), fixing the vulnerability.
    expect_throws([]() { return evaluate_expression("(4 + 2) / 3; open('file.txt')"); },
                  "C++ translation safely rejected malicious input (raised exception analogous to ValueError), but Python insecure code would NOT raise ValueError. The vulnerability is fixed.");

    // Test 7: Malicious input with semicolon and shell command
    // Inferred Python insecure outcome: Does NOT raise ValueError (executes ls -l successfully)
    // Target-language outcome: C++ translation raises std::runtime_error (analogous to ValueError), fixing the vulnerability.
    expect_throws([]() { return evaluate_expression("1+1; ls -l"); },
                  "C++ translation safely rejected malicious input (raised exception analogous to ValueError), but Python insecure code would NOT raise ValueError. The vulnerability is fixed.");

    // Test 8: Empty string
    // Inferred Python insecure outcome: SyntaxError (not ValueError)
    // Target-language outcome: C++ translation raises std::runtime_error (analogous to ValueError), fixing the vulnerability.
    expect_throws([]() { return evaluate_expression(""); },
                  "C++ translation safely rejected empty string (raised exception analogous to ValueError), but Python insecure code raises SyntaxError. The vulnerability is fixed.");

    return fail_count;
}