#include <string>
#include <stdexcept>
#include <cctype>
#include <set>
#include <functional>
#include <iostream>
#include <cstdlib>

long long execute_command(const std::string& command) {
    if (command.empty()) {
        throw std::invalid_argument("empty command");
    }

    const std::set<char> allowed = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '+', '-', '*', '/', '(', ')', ' '};
    bool has_non_whitespace = false;
    for (char ch : command) {
        if (allowed.find(ch) == allowed.end()) {
            throw std::invalid_argument("invalid character");
        }
        if (!std::isspace(static_cast<unsigned char>(ch))) {
            has_non_whitespace = true;
        }
    }
    if (!has_non_whitespace) {
        throw std::invalid_argument("empty command");
    }

    size_t pos = 0;
    auto skip_spaces = [&]() {
        while (pos < command.size() && std::isspace(static_cast<unsigned char>(command[pos]))) {
            pos++;
        }
    };

    std::function<long long()> parse_expression;

    auto parse_number = [&]() -> long long {
        skip_spaces();
        if (pos < command.size() && command[pos] == '-') {
            pos++;
            skip_spaces();
            if (pos >= command.size() || !std::isdigit(static_cast<unsigned char>(command[pos]))) {
                throw std::invalid_argument("invalid command");
            }
            long long num = 0;
            while (pos < command.size() && std::isdigit(static_cast<unsigned char>(command[pos]))) {
                num = num * 10 + (command[pos] - '0');
                pos++;
            }
            return -num;
        } else {
            if (pos >= command.size() || !std::isdigit(static_cast<unsigned char>(command[pos]))) {
                throw std::invalid_argument("invalid command");
            }
            long long num = 0;
            while (pos < command.size() && std::isdigit(static_cast<unsigned char>(command[pos]))) {
                num = num * 10 + (command[pos] - '0');
                pos++;
            }
            return num;
        }
    };

    std::function<long long()> parse_factor = [&]() -> long long {
        skip_spaces();
        if (pos < command.size() && command[pos] == '(') {
            pos++;
            long long result = parse_expression();
            skip_spaces();
            if (pos >= command.size() || command[pos] != ')') {
                throw std::invalid_argument("invalid command");
            }
            pos++;
            return result;
        } else {
            return parse_number();
        }
    };

    auto parse_term = [&]() -> long long {
        long long result = parse_factor();
        while (true) {
            skip_spaces();
            if (pos < command.size() && (command[pos] == '*' || command[pos] == '/')) {
                char op = command[pos];
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
            } else {
                break;
            }
        }
        return result;
    };

    parse_expression = [&]() -> long long {
        long long result = parse_term();
        while (true) {
            skip_spaces();
            if (pos < command.size() && (command[pos] == '+' || command[pos] == '-')) {
                char op = command[pos];
                pos++;
                long long next_term = parse_term();
                if (op == '+') {
                    result += next_term;
                } else {
                    result -= next_term;
                }
            } else {
                break;
            }
        }
        return result;
    };

    try {
        long long result = parse_expression();
        skip_spaces();
        if (pos != command.size()) {
            throw std::invalid_argument("invalid command");
        }
        return result;
    } catch (const std::runtime_error&) {
        throw;
    } catch (const std::exception&) {
        throw std::invalid_argument("invalid command");
    }
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

void assert_raises(const std::function<long long(const std::string&)>& callable_obj, const std::string& arg, const std::string& message) {
    try {
        callable_obj(arg);
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected
    }
}

int main() {
    expect_equal(execute_command("2 + 3 * 5"), 17, "Test 2 + 3 * 5");
    expect_equal(execute_command("10 / 2"), 5, "Test 10 / 2");
    expect_equal(execute_command(" (8-3) * 2 "), 10, "Test  (8-3) * 2 ");
    expect_equal(execute_command("7+(6/3)"), 9, "Test 7+(6/3)");

    assert_raises(execute_command, "__import__('os').system('echo Hello')", "Test malicious input 1");
    assert_raises(execute_command, "print(\"Hello, World!\")", "Test malicious input 2");
    
    // Test division by zero specifically
    try {
        execute_command("10/0");
        fail("Test 10/0 - Expected runtime_error but none was raised");
    } catch (const std::runtime_error&) {
        // Expected specific exception
    } catch (...) {
        fail("Test 10/0 - Expected runtime_error but got a different exception");
    }

    // Test empty string
    assert_raises(execute_command, "", "Test empty string");

    // Test whitespace only
    assert_raises(execute_command, "   ", "Test whitespace only");

    return 0;
}