#include <string>
#include <stdexcept>
#include <cctype>
#include <set>
#include <functional>
#include <iostream>

long long evaluate_expression(const std::string& expression) {
    if (expression.empty()) {
        throw std::invalid_argument("empty expression");
    }

    const std::set<char> allowed_chars = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '+', '-', '*', '/', '(', ')', ' '};
    bool has_non_whitespace = false;
    for (char ch : expression) {
        if (allowed_chars.find(ch) == allowed_chars.end()) {
            throw std::invalid_argument("invalid character");
        }
        if (!std::isspace(static_cast<unsigned char>(ch))) {
            has_non_whitespace = true;
        }
    }
    if (!has_non_whitespace) {
        throw std::invalid_argument("empty expression");
    }

    std::size_t pos = 0;

    std::function<long long()> parse_expression;

    auto parse_number = [&]() -> long long {
        std::size_t start = pos;
        while (pos < expression.size() && std::isdigit(static_cast<unsigned char>(expression[pos]))) {
            pos++;
        }
        if (start == pos) {
            throw std::invalid_argument("invalid expression");
        }
        return std::stoll(expression.substr(start, pos - start));
    };

    auto parse_factor = [&]() -> long long {
        while (pos < expression.size() && std::isspace(static_cast<unsigned char>(expression[pos]))) {
            pos++;
        }
        if (pos >= expression.size()) {
            throw std::invalid_argument("invalid expression");
        }

        bool negative = false;
        if (expression[pos] == '-') {
            negative = true;
            pos++;
            while (pos < expression.size() && std::isspace(static_cast<unsigned char>(expression[pos]))) {
                pos++;
            }
        } else if (expression[pos] == '+') {
            pos++;
            while (pos < expression.size() && std::isspace(static_cast<unsigned char>(expression[pos]))) {
                pos++;
            }
        }

        long long result;
        if (pos < expression.size() && expression[pos] == '(') {
            pos++;
            result = parse_expression();
            while (pos < expression.size() && std::isspace(static_cast<unsigned char>(expression[pos]))) {
                pos++;
            }
            if (pos >= expression.size() || expression[pos] != ')') {
                throw std::invalid_argument("invalid expression");
            }
            pos++;
        } else if (pos < expression.size() && std::isdigit(static_cast<unsigned char>(expression[pos]))) {
            result = parse_number();
        } else {
            throw std::invalid_argument("invalid expression");
        }

        return negative ? -result : result;
    };

    auto parse_term = [&]() -> long long {
        long long result = parse_factor();
        while (pos < expression.size()) {
            while (pos < expression.size() && std::isspace(static_cast<unsigned char>(expression[pos]))) {
                pos++;
            }
            if (pos >= expression.size()) break;

            char op = expression[pos];
            if (op != '*' && op != '/') break;
            pos++;

            long long next_factor = parse_factor();
            if (op == '*') {
                result *= next_factor;
            } else {
                if (next_factor == 0) {
                    throw std::runtime_error("division by zero");
                }
                result /= next_factor;
            }
        }
        return result;
    };

    parse_expression = [&]() -> long long {
        long long result = parse_term();
        while (pos < expression.size()) {
            while (pos < expression.size() && std::isspace(static_cast<unsigned char>(expression[pos]))) {
                pos++;
            }
            if (pos >= expression.size()) break;

            char op = expression[pos];
            if (op != '+' && op != '-') break;
            pos++;

            long long next_term = parse_term();
            if (op == '+') {
                result += next_term;
            } else {
                result -= next_term;
            }
        }
        return result;
    };

    long long final_result = parse_expression();

    while (pos < expression.size() && std::isspace(static_cast<unsigned char>(expression[pos]))) {
        pos++;
    }
    if (pos != expression.size()) {
        throw std::invalid_argument("invalid expression");
    }

    return final_result;
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(long long actual, long long expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
    }
}

void assert_raises(const std::function<long long()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    }
}

int main() {
    expect_equal(evaluate_expression("2 + 3 * (5 - 1)"), 14, "Test 1 failed");
    expect_equal(evaluate_expression("(4 + 2) / 3"), 2, "Test 2 failed");
    expect_equal(evaluate_expression(" 10/(2+3) "), 2, "Test 3 failed");
    expect_equal(evaluate_expression("7 - (2*3) + 1"), 2, "Test 4 failed");

    assert_raises([]() { return evaluate_expression("(4 + 2) / 0"); }, "Test 5 failed: Division by zero");
    assert_raises([]() { return evaluate_expression("(4 + 2) / 3; open('file.txt')"); }, "Test 6 failed: Invalid character");
    assert_raises([]() { return evaluate_expression("1+1; ls -l"); }, "Test 7 failed: Invalid character");
    assert_raises([]() { return evaluate_expression(""); }, "Test 8 failed: Empty expression");

    return 0;
}