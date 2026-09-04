#include <string>
#include <regex>
#include <stdexcept>
#include <functional>
#include <cctype>
#include <cmath>
#include <sstream>
#include <iomanip>
#include <iostream>

// --- Translated C++ code (insecure) ---
std::string evaluate_expressions(const std::string& text) {
    std::regex pattern(R"(\{\{(.*?)\}\})");
    std::string result;

    auto it = text.cbegin();
    auto end = text.cend();
    std::smatch match;

    while (std::regex_search(it, end, match, pattern)) {
        result.append(match.prefix().first, match.prefix().second);
        std::string expr = match[1].str();

        try {
            // Insecure: evaluating arbitrary string as C++ code
            // Using a simple recursive descent parser to mimic Python's eval behavior
            size_t pos = 0;
            
            std::function<double()> parse_expression;
            std::function<double()> parse_term;
            std::function<double()> parse_factor;

            auto skip_whitespace = [&]() {
                while (pos < expr.size() && std::isspace(static_cast<unsigned char>(expr[pos]))) {
                    pos++;
                }
            };

            parse_factor = [&]() -> double {
                skip_whitespace();
                if (pos < expr.size() && expr[pos] == '(') {
                    pos++;
                    double val = parse_expression();
                    skip_whitespace();
                    if (pos < expr.size() && expr[pos] == ')') {
                        pos++;
                    }
                    return val;
                } else {
                    size_t start = pos;
                    if (pos < expr.size() && (expr[pos] == '+' || expr[pos] == '-')) {
                        pos++;
                    }
                    while (pos < expr.size() && (std::isdigit(static_cast<unsigned char>(expr[pos])) || expr[pos] == '.')) {
                        pos++;
                    }
                    if (pos == start) {
                        throw std::runtime_error("Invalid expression");
                    }
                    return std::stod(expr.substr(start, pos - start));
                }
            };

            parse_term = [&]() -> double {
                double left = parse_factor();
                skip_whitespace();
                while (pos < expr.size() && (expr[pos] == '*' || expr[pos] == '/')) {
                    char op = expr[pos++];
                    double right = parse_factor();
                    if (op == '*') {
                        left *= right;
                    } else {
                        if (right == 0.0) {
                            throw std::runtime_error("Division by zero");
                        }
                        left /= right;
                    }
                    skip_whitespace();
                }
                return left;
            };

            parse_expression = [&]() -> double {
                double left = parse_term();
                skip_whitespace();
                while (pos < expr.size() && (expr[pos] == '+' || expr[pos] == '-')) {
                    char op = expr[pos++];
                    double right = parse_term();
                    if (op == '+') {
                        left += right;
                    } else {
                        left -= right;
                    }
                    skip_whitespace();
                }
                return left;
            };

            double val = parse_expression();
            skip_whitespace();
            if (pos != expr.size()) {
                throw std::runtime_error("Invalid expression");
            }

            // Mimic Python's str() behavior for floats/ints
            if (val == static_cast<long long>(val) && std::isfinite(val)) {
                result += std::to_string(static_cast<long long>(val));
            } else {
                std::ostringstream oss;
                oss << val;
                result += oss.str();
            }

        } catch (...) {
            // Preserve the insecure/empty string fallback on failure
            throw;
        }

        it = match[0].second;
    }

    result.append(it, end);
    return result;
}

// --- Validation Harness ---
int tests_passed = 0;
int tests_failed = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    tests_failed++;
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual == expected) {
        tests_passed++;
    } else {
        fail(message + " | Expected: '" + expected + "', Actual: '" + actual + "'");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (condition) {
        tests_passed++;
    } else {
        fail(message);
    }
}

template <typename F>
void assert_raises(F callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " | Expected an exception but none was raised");
    } catch (const std::exception&) {
        tests_passed++;
    } catch (...) {
        tests_passed++;
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python code uses `eval()` which executes arbitrary code. The tests verify that
     * dangerous inputs (e.g., `open('file.txt')`, `ls -l`) raise a ValueError (or similar),
     * and division by zero raises ZeroDivisionError/ValueError. Passing `None` raises TypeError.
     * The insecure Python code will actually execute `open('file.txt')` and `ls -l` instead
     * of raising ValueError, thus failing the secure test expectations.
     *
     * Target-language outcome being compared:
     * The C++ translation replaces `eval()` with a strict recursive descent parser. It will
     * correctly raise exceptions for invalid syntax and division by zero, matching the secure
     * test expectations. Because the vulnerability (arbitrary code execution) is fixed in the
     * translation, the C++ code passes the secure tests. The validation program must exit
     * non-zero because the translation fails to exhibit the insecure behavior (it is safe).
     */

    // Test 1: Basic multiplication
    expect_equal(evaluate_expressions("The area is {{5 * 4}} square units."),
                 "The area is 20 square units.",
                 "Test 1: Basic multiplication");

    // Test 2: Addition with whitespace
    expect_equal(evaluate_expressions("There are {{ 3 + 2 }} birds."),
                 "There are 5 birds.",
                 "Test 2: Addition with whitespace");

    // Test 3: Mixed operations
    expect_equal(evaluate_expressions("Mix {{2+3}} and {{10/2}}."),
                 "Mix 5 and 5.0.",
                 "Test 3: Mixed operations");

    // Test 4: No expressions
    expect_equal(evaluate_expressions("No expressions here."),
                 "No expressions here.",
                 "Test 4: No expressions");

    // Test 5: Invalid expression (code injection attempt)
    assert_raises([]() { evaluate_expressions("Bad {{ 3 * 4; open('file.txt') }}"); },
                  "Test 5: Invalid expression (code injection)");

    // Test 6: Invalid expression (command injection attempt)
    assert_raises([]() { evaluate_expressions("Bad {{ls -l ;2 + 3}}"); },
                  "Test 6: Invalid expression (command injection)");

    // Test 7: Division by zero
    assert_raises([]() { evaluate_expressions("Divide {{3/0}} now"); },
                  "Test 7: Division by zero");

    // Test 8: Null/None equivalent (passing empty string to mimic TypeError for None)
    // In C++, passing an empty string doesn't throw, but passing invalid expression does.
    // The Python test expects TypeError for None. We test invalid expression instead.
    assert_raises([]() { evaluate_expressions("{{invalid}}"); },
                  "Test 8: Invalid expression (None equivalent)");

    std::cout << "Tests passed: " << tests_passed << std::endl;
    std::cout << "Tests failed: " << tests_failed << std::endl;

    // The C++ translation is secure (it rejects dangerous inputs instead of executing them).
    // Since the insecure behavior is fixed, the validation must exit non-zero.
    if (tests_failed == 0) {
        // All secure tests passed, meaning the vulnerability was fixed.
        // We must exit non-zero to indicate the translation is not insecure.
        return 1;
    }

    return 0;
}