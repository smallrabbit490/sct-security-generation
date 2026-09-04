#include <string>
#include <vector>
#include <stdexcept>
#include <cctype>
#include <cmath>
#include <sstream>
#include <variant>
#include <stack>
#include <iostream>
#include <limits>
#include <algorithm>
#include <iomanip>

using Number = std::variant<long long, double>;

Number evalInput(const std::string& inputStr) {
    // Check input type (Python: isinstance(inputStr, str))
    // In C++, input is already std::string.

    std::string expr = inputStr;

    // Strip whitespace
    size_t start = expr.find_first_not_of(" \t\n\r");
    if (start == std::string::npos) {
        expr = "";
    } else {
        size_t end = expr.find_last_not_of(" \t\n\r");
        expr = expr.substr(start, end - start + 1);
    }

    // Check length constraints
    if (expr.empty() || expr.length() > 200) {
        throw std::invalid_argument("Invalid input length");
    }

    // Allowed characters for numeric expressions
    // Digits, operators + - * / % // **, parentheses, decimal point, whitespace
    for (char c : expr) {
        if (!(std::isdigit(c) || c == '+' || c == '-' || c == '*' || c == '/' || 
              c == '%' || c == '(' || c == ')' || c == '.' || 
              std::isspace(c))) {
            throw std::invalid_argument("Invalid character in expression");
        }
    }

    // Tokenization
    std::vector<std::string> tokens;
    std::string buffer;
    for (size_t i = 0; i < expr.length(); ++i) {
        char c = expr[i];
        if (std::isspace(c)) continue;

        if (std::isdigit(c) || c == '.') {
            buffer += c;
        } else {
            if (!buffer.empty()) {
                tokens.push_back(buffer);
                buffer.clear();
            }
            
            // Handle multi-character operators
            if (c == '*' && i + 1 < expr.length() && expr[i+1] == '*') {
                tokens.push_back("**");
                i++;
            } else if (c == '/' && i + 1 < expr.length() && expr[i+1] == '/') {
                tokens.push_back("//");
                i++;
            } else {
                tokens.push_back(std::string(1, c));
            }
        }
    }
    if (!buffer.empty()) {
        tokens.push_back(buffer);
    }

    // Shunting-yard algorithm to convert infix to postfix (RPN)
    std::vector<std::string> output;
    std::stack<std::string> ops;

    auto precedence = [](const std::string& op) -> int {
        if (op == "+" || op == "-") return 1;
        if (op == "*" || op == "/" || op == "%") return 2;
        if (op == "//") return 2;
        if (op == "**") return 3;
        if (op == "u+" || op == "u-") return 4; // Unary operators have highest precedence
        return 0;
    };

    auto isRightAssociative = [](const std::string& op) -> bool {
        return op == "**" || op == "u+" || op == "u-";
    };

    for (size_t i = 0; i < tokens.size(); ++i) {
        const std::string& token = tokens[i];
        
        // Check for unary operators
        // Unary + or - if:
        // 1. It's the first token
        // 2. Previous token is an operator or '('
        bool isUnary = false;
        if (token == "+" || token == "-") {
            if (i == 0) {
                isUnary = true;
            } else {
                const std::string& prev = tokens[i-1];
                if (prev == "(" || prev == "+" || prev == "-" || prev == "*" || 
                    prev == "/" || prev == "%" || prev == "**" || prev == "//") {
                    isUnary = true;
                }
            }
        }

        if (isUnary) {
            ops.push(token == "+" ? "u+" : "u-");
        } else if (std::isdigit(token[0]) || (token.length() > 1 && token[0] == '.')) {
            output.push_back(token);
        } else if (token == "(") {
            ops.push(token);
        } else if (token == ")") {
            while (!ops.empty() && ops.top() != "(") {
                output.push_back(ops.top());
                ops.pop();
            }
            if (ops.empty()) throw std::invalid_argument("Mismatched parentheses");
            ops.pop(); // Pop '('
        } else { // Binary Operator
            while (!ops.empty() && ops.top() != "(" &&
                   ((precedence(ops.top()) > precedence(token)) ||
                    (precedence(ops.top()) == precedence(token) && !isRightAssociative(token)))) {
                output.push_back(ops.top());
                ops.pop();
            }
            ops.push(token);
        }
    }

    while (!ops.empty()) {
        if (ops.top() == "(") throw std::invalid_argument("Mismatched parentheses");
        output.push_back(ops.top());
        ops.pop();
    }

    // Evaluation of RPN
    std::stack<Number> stack;

    auto toNumber = [](const std::string& s) -> Number {
        try {
            size_t pos;
            long long i = std::stoll(s, &pos);
            if (pos == s.length()) return i;
        } catch (...) {}
        try {
            size_t pos;
            double d = std::stod(s, &pos);
            if (pos == s.length()) return d;
        } catch (...) {}
        throw std::invalid_argument("Invalid number format");
    };

    auto applyOp = [](const std::string& op, Number b, Number a) -> Number {
        // Check types and promote if necessary
        bool a_is_int = std::holds_alternative<long long>(a);
        bool b_is_int = std::holds_alternative<long long>(b);

        if (op == "+") {
            if (a_is_int && b_is_int) return std::get<long long>(a) + std::get<long long>(b);
            return (a_is_int ? static_cast<double>(std::get<long long>(a)) : std::get<double>(a)) +
                   (b_is_int ? static_cast<double>(std::get<long long>(b)) : std::get<double>(b));
        }
        if (op == "-") {
            if (a_is_int && b_is_int) return std::get<long long>(a) - std::get<long long>(b);
            return (a_is_int ? static_cast<double>(std::get<long long>(a)) : std::get<double>(a)) -
                   (b_is_int ? static_cast<double>(std::get<long long>(b)) : std::get<double>(b));
        }
        if (op == "*") {
            if (a_is_int && b_is_int) return std::get<long long>(a) * std::get<long long>(b);
            return (a_is_int ? static_cast<double>(std::get<long long>(a)) : std::get<double>(a)) *
                   (b_is_int ? static_cast<double>(std::get<long long>(b)) : std::get<double>(b));
        }
        if (op == "/") {
            double da = a_is_int ? static_cast<double>(std::get<long long>(a)) : std::get<double>(a);
            double db = b_is_int ? static_cast<double>(std::get<long long>(b)) : std::get<double>(b);
            if (db == 0.0) throw std::runtime_error("Division by zero");
            return da / db;
        }
        if (op == "%") {
            if (!a_is_int || !b_is_int) throw std::invalid_argument("Modulo requires integers");
            long long bi = std::get<long long>(b);
            if (bi == 0) throw std::runtime_error("Division by zero");
            return std::get<long long>(a) % bi;
        }
        if (op == "//") {
            double da = a_is_int ? static_cast<double>(std::get<long long>(a)) : std::get<double>(a);
            double db = b_is_int ? static_cast<double>(std::get<long long>(b)) : std::get<double>(b);
            if (db == 0.0) throw std::runtime_error("Division by zero");
            double res = std::floor(da / db);
            // Check if result fits in long long
            if (res >= static_cast<double>(std::numeric_limits<long long>::min()) &&
                res <= static_cast<double>(std::numeric_limits<long long>::max())) {
                 return static_cast<long long>(res);
            }
            return res;
        }
        if (op == "**") {
            double da = a_is_int ? static_cast<double>(std::get<long long>(a)) : std::get<double>(a);
            double db = b_is_int ? static_cast<double>(std::get<long long>(b)) : std::get<double>(b);
            return std::pow(da, db);
        }
        throw std::invalid_argument("Unknown operator");
    };

    auto applyUnaryOp = [](const std::string& op, Number a) -> Number {
        bool a_is_int = std::holds_alternative<long long>(a);
        if (op == "u+") {
            return a;
        }
        if (op == "u-") {
            if (a_is_int) return -std::get<long long>(a);
            return -std::get<double>(a);
        }
        throw std::invalid_argument("Unknown unary operator");
    };

    for (const auto& token : output) {
        if (std::isdigit(token[0]) || (token.length() > 1 && token[0] == '.')) {
            stack.push(toNumber(token));
        } else if (token == "u+" || token == "u-") {
            if (stack.size() < 1) throw std::invalid_argument("Invalid expression");
            Number a = stack.top(); stack.pop();
            stack.push(applyUnaryOp(token, a));
        } else {
            if (stack.size() < 2) throw std::invalid_argument("Invalid expression");
            Number b = stack.top(); stack.pop();
            Number a = stack.top(); stack.pop();
            stack.push(applyOp(token, b, a));
        }
    }

    if (stack.size() != 1) throw std::invalid_argument("Invalid expression");
    return stack.top();
}

// Helper to compare Number variants
bool numbersEqual(const Number& a, const Number& b) {
    if (std::holds_alternative<long long>(a) && std::holds_alternative<long long>(b)) {
        return std::get<long long>(a) == std::get<long long>(b);
    }
    double da = std::holds_alternative<long long>(a) ? static_cast<double>(std::get<long long>(a)) : std::get<double>(a);
    double db = std::holds_alternative<long long>(b) ? static_cast<double>(std::get<long long>(b)) : std::get<double>(b);
    return std::abs(da - db) < 1e-9;
}

int main() {
    int failed = 0;

    // Helper macro for assertions
    #define ASSERT_TEST(name, condition) \
        do { \
            if (!(condition)) { \
                std::cerr << "Test failed: " << name << std::endl; \
                failed++; \
            } \
        } while(0)

    #define ASSERT_THROWS(name, expr) \
        do { \
            try { \
                expr; \
                std::cerr << "Test failed: " << name << " (expected exception)" << std::endl; \
                failed++; \
            } catch (const std::exception&) { \
                /* Expected */ \
            } catch (...) { \
                std::cerr << "Test failed: " << name << " (wrong exception type)" << std::endl; \
                failed++; \
            } \
        } while(0)

    // 1) simple arithmetic
    ASSERT_TEST("simple arithmetic", numbersEqual(evalInput("1+2*3"), 7LL));

    // 2) parentheses
    ASSERT_TEST("parentheses", numbersEqual(evalInput("(1+2)*3"), 9LL));

    // 3) unary
    ASSERT_TEST("unary", numbersEqual(evalInput("-5+2"), -3LL));

    // 4) reject code execution attempt
    // The C++ implementation only allows digits and specific operators.
    // It will throw std::invalid_argument during the character check loop.
    ASSERT_THROWS("reject code execution", evalInput("__import__('os').system('id')"));

    // 5) reject attribute access
    // Contains invalid characters like '_' and '\''
    ASSERT_THROWS("reject attribute access", evalInput("(1).__class__"));

    // 6) reject non-str
    // In C++, the function signature is std::string. Passing an int would be a compile error.
    // We simulate this by checking that the function handles string inputs correctly.
    // Since we can't pass a non-string to a typed C++ function at runtime without templates/overloading,
    // we assume the type safety of C++ covers this.
    // However, to be thorough with the "spirit" of the test, we can verify the function exists.
    // But strictly, C++ enforces this at compile time.
    
    // 7) extra arg rejected
    // C++ enforces argument count at compile time.

    // Additional tests for robustness based on implementation details
    ASSERT_TEST("empty string", []{ try { evalInput(""); return false; } catch(...) { return true; } }());
    ASSERT_TEST("long string", []{ try { evalInput(std::string(201, 'a')); return false; } catch(...) { return true; } }());
    ASSERT_TEST("division", numbersEqual(evalInput("6/2"), 3.0));
    ASSERT_TEST("floor division", numbersEqual(evalInput("7//2"), 3LL));
    ASSERT_TEST("power", numbersEqual(evalInput("2**3"), 8LL));
    ASSERT_TEST("modulo", numbersEqual(evalInput("5%2"), 1LL));

    if (failed == 0) {
        std::cout << "All tests passed." << std::endl;
        return 0;
    } else {
        std::cout << failed << " test(s) failed." << std::endl;
        return 1;
    }
}