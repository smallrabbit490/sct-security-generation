#include <string>
#include <vector>
#include <stack>
#include <map>
#include <cctype>
#include <stdexcept>
#include <iostream>
#include <cmath>
#include <functional>

// --- Translated C++ code (insecure) ---
bool is_operator(char c) {
    return c == '+' || c == '-' || c == '*' || c == '/';
}

double perform_operation(char op, double operand1, double operand2) {
    if (op == '+') return operand1 + operand2;
    if (op == '-') return operand1 - operand2;
    if (op == '*') return operand1 * operand2;
    if (op == '/') return operand1 / operand2;
    throw std::runtime_error("Invalid operator");
}

std::string infix_to_postfix(const std::string& expression) {
    std::map<char, int> priority = {{'+', 1}, {'-', 1}, {'*', 2}, {'/', 2}};
    std::stack<char> stack;
    std::string postfix;
    for (char c : expression) {
        if (std::isdigit(static_cast<unsigned char>(c))) {
            postfix += c;
        } else if (is_operator(c)) {
            while (!stack.empty() && is_operator(stack.top()) && priority[c] <= priority[stack.top()]) {
                postfix += stack.top();
                stack.pop();
            }
            stack.push(c);
        }
    }
    while (!stack.empty()) {
        postfix += stack.top();
        stack.pop();
    }
    return postfix;
}

double evaluate_postfix(const std::string& postfix) {
    std::stack<double> stack;
    for (char c : postfix) {
        if (std::isdigit(static_cast<unsigned char>(c))) {
            stack.push(static_cast<double>(c - '0'));
        } else if (is_operator(c)) {
            if (stack.size() < 2) {
                throw std::runtime_error("Invalid expression");
            }
            double operand2 = stack.top();
            stack.pop();
            double operand1 = stack.top();
            stack.pop();
            double result = perform_operation(c, operand1, operand2);
            stack.push(result);
        }
    }
    if (stack.size() != 1) {
        throw std::runtime_error("Invalid expression");
    }
    return stack.top();
}

double evaluate_expression(std::string expression) {
    std::string cleaned_expression;
    for (char c : expression) {
        if (c != ' ') {
            cleaned_expression += c;
        }
    }
    std::string postfix_expression = infix_to_postfix(cleaned_expression);
    return evaluate_postfix(postfix_expression);
}
// --- End of translated C++ code ---


// --- Validation Harness Helpers ---
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(double actual, double expected, const std::string& message) {
    if (std::abs(actual - expected) > 1e-9) {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<double(std::string)>& callable_obj, const std::string& arg, const std::string& message) {
    bool raised = false;
    try {
        callable_obj(arg);
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message + " - Expected an exception but none was raised");
    }
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python code lacks proper input validation and error handling for malformed expressions.
     * For inputs like "2 + * 3", "3++2", or "", it fails with unhandled exceptions 
     * (IndexError, ZeroDivisionError, etc.) rather than raising a clean, intended ValueError.
     * 
     * Target-language insecure outcome being compared:
     * The C++ translation similarly lacks robust input validation. For malformed inputs,
     * it exhibits undefined behavior (e.g., calling top() on an empty stack) or crashes 
     * (e.g., SIGABRT from standard library assertions) instead of throwing a well-defined 
     * std::exception. The validation checks that these malformed inputs do NOT succeed 
     * silently and DO result in an exception or failure, matching the insecure behavior 
     * of failing ungracefully on bad inputs.
     */

    // Valid expression tests
    expect_equal(evaluate_expression("3 + 4 * 2 - 6 / 2"), 8.0, "Test 1 failed");
    expect_equal(evaluate_expression("2+3*4/2"), 8.0, "Test 2 failed");
    expect_equal(evaluate_expression(" 3/2 "), 1.5, "Test 3 failed");
    expect_equal(evaluate_expression(" 3+5/2 "), 5.5, "Test 4 failed");

    // Insecure behavior / exception tests
    // For "2+3*4/0", the C++ code will perform division by zero (double), resulting in inf.
    // This is insecure behavior (no exception raised), so we verify it doesn't throw and yields inf.
    try {
        double res = evaluate_expression("2+3*4/0");
        expect_true(std::isinf(res), "Test 5 failed: Expected inf for division by zero, got finite value");
    } catch (const std::exception&) {
        fail("Test 5 failed: Exception raised for division by zero, but C++ double division should yield inf");
    }

    // For malformed expressions, the insecure C++ code should fail/crash/throw, not return a valid result.
    // Note: If the code crashes due to UB (like stack assertion failure), the process terminates abruptly.
    assert_raises(evaluate_expression, "2 + * 3", "Test 6 failed: Malformed expression '2 + * 3' did not raise");
    assert_raises(evaluate_expression, "3++2", "Test 7 failed: Malformed expression '3++2' did not raise");
    assert_raises(evaluate_expression, "", "Test 8 failed: Empty expression did not raise");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}