#include <string>
#include <vector>
#include <stdexcept>
#include <cctype>
#include <cmath>
#include <iostream>
#include <functional>

double evaluate_expression(const std::string& expression) {
    auto is_operator = [](char ch) {
        return ch == '+' || ch == '-' || ch == '*' || ch == '/';
    };

    auto precedence = [](char op) {
        return (op == '*' || op == '/') ? 2 : 1;
    };

    std::string s;
    s.reserve(expression.size());
    for (char ch : expression) {
        if (!std::isspace(static_cast<unsigned char>(ch))) {
            s += ch;
        }
    }

    if (s.empty()) {
        throw std::invalid_argument("empty expression");
    }

    for (char ch : s) {
        if (!std::isdigit(static_cast<unsigned char>(ch)) && !is_operator(ch)) {
            throw std::invalid_argument("invalid character");
        }
    }

    std::vector<double> values;
    std::vector<char> ops;
    bool expect_number = true;

    auto apply_top = [&]() {
        if (ops.empty()) {
            throw std::invalid_argument("malformed expression");
        }
        char op = ops.back();
        ops.pop_back();

        if (values.size() < 2) {
            throw std::invalid_argument("malformed expression");
        }
        double b = values.back();
        values.pop_back();
        double a = values.back();
        values.pop_back();

        if (op == '+') {
            values.push_back(a + b);
        } else if (op == '-') {
            values.push_back(a - b);
        } else if (op == '*') {
            values.push_back(a * b);
        } else if (op == '/') {
            if (b == 0) {
                throw std::runtime_error("division by zero");
            }
            values.push_back(a / b);
        } else {
            throw std::invalid_argument("invalid operator");
        }
    };

    for (char ch : s) {
        if (std::isdigit(static_cast<unsigned char>(ch))) {
            if (!expect_number) {
                throw std::invalid_argument("malformed expression");
            }
            values.push_back(static_cast<double>(ch - '0'));
            expect_number = false;
        } else {
            if (expect_number) {
                throw std::invalid_argument("malformed expression");
            }
            while (!ops.empty() && precedence(ops.back()) >= precedence(ch)) {
                apply_top();
            }
            ops.push_back(ch);
            expect_number = true;
        }
    }

    if (expect_number) {
        throw std::invalid_argument("malformed expression");
    }

    while (!ops.empty()) {
        if (values.size() < 2) {
            throw std::invalid_argument("malformed expression");
        }
        apply_top();
    }

    if (values.size() != 1) {
        throw std::invalid_argument("malformed expression");
    }

    return values[0];
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

void expect_equal(double actual, double expected, const std::string& message) {
    if (std::abs(actual - expected) > 1e-9) {
        fail(message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
    }
}

void assert_raises(const std::function<double(const std::string&)>& callable_obj, const std::string& arg, const std::string& message) {
    try {
        callable_obj(arg);
        fail(message + " (expected an exception but none was raised)");
    } catch (const std::exception&) {
        // Expected exception caught
    }
}

int main() {
    expect_equal(evaluate_expression("3 + 4 * 2 - 6 / 2"), 8.0, "Test 1 failed");
    expect_equal(evaluate_expression("2+3*4/2"), 8.0, "Test 2 failed");
    expect_equal(evaluate_expression(" 3/2 "), 1.5, "Test 3 failed");
    expect_equal(evaluate_expression(" 3+5/2 "), 5.5, "Test 4 failed");

    assert_raises(evaluate_expression, "2+3*4/0", "Test 5 failed");
    assert_raises(evaluate_expression, "2 + * 3", "Test 6 failed");
    assert_raises(evaluate_expression, "3++2", "Test 7 failed");
    assert_raises(evaluate_expression, "", "Test 8 failed");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}