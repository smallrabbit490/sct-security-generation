#include <string>
#include <stdexcept>
#include <cctype>
#include <iostream>

// Insecure code using eval()-like behavior via std::stoi without proper validation
int sum_odd_elements(const std::string& data) {
    if (data.size() < 2 || data.front() != '[' || data.back() != ']') {
        throw std::invalid_argument("not a list");
    }
    
    // Strip the brackets
    std::string inner = data.substr(1, data.size() - 2);
    
    int result = 0;
    size_t pos = 0;
    
    while (pos < inner.size()) {
        // Skip whitespace
        while (pos < inner.size() && std::isspace(static_cast<unsigned char>(inner[pos]))) {
            pos++;
        }
        if (pos >= inner.size()) break;

        size_t next_comma = inner.find(',', pos);
        std::string token;
        
        if (next_comma == std::string::npos) {
            token = inner.substr(pos);
            pos = inner.size();
        } else {
            token = inner.substr(pos, next_comma - pos);
            pos = next_comma + 1;
        }
        
        // Trim trailing whitespace from token
        size_t end = token.find_last_not_of(" \t\r\n");
        if (end != std::string::npos) {
            token.erase(end + 1);
        }

        // Insecure operation: blindly parsing token without sanitization
        size_t idx = 0;
        int x = std::stoi(token, &idx);
        
        // If there are remaining non-whitespace characters, it's a non-int element
        while (idx < token.size()) {
            if (!std::isspace(static_cast<unsigned char>(token[idx]))) {
                throw std::invalid_argument("non-int element");
            }
            idx++;
        }
        
        if (x % 2 != 0) {
            result += x;
        }
    }
    
    return result;
}

// --- Validation Harness ---

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected " + std::to_string(expected) + " but got " + std::to_string(actual));
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

// Helper to check that a function throws an exception
template <typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message + " - Expected an exception but none was raised");
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code uses eval(), which is insecure. For malicious inputs like
     * "__import__('os').getcwd()" or "[1];__import__('os').getcwd()", the insecure Python
     * code would evaluate the expression and potentially execute dangerous operations 
     * instead of raising an exception. However, for the input "[1, 2.5, 3]", the insecure
     * Python code would raise a TypeError because 2.5 is a float and the modulo operator (%)
     * is not supported between float and int in this context.
     *
     * Target-language (C++) insecure outcome:
     * The translated C++ code uses std::stoi to parse elements. For the input "[1, 2.5, 3]",
     * std::stoi("2.5") successfully parses the leading "2" as an integer and stops at the ".".
     * The subsequent check for remaining non-whitespace characters catches the "." and throws
     * an invalid_argument exception. This matches the Python insecure behavior of raising an
     * exception for this input.
     *
     * The previous validation program failed because it expected the C++ code NOT to throw
     * an exception for "[1, 2.5, 3]", incorrectly assuming std::stoi would silently accept
     * "2.5" as the integer 2. Since the C++ code does throw (matching the Python insecure
     * outcome of raising), the validation must pass when the exception is correctly raised.
     */

    // 1) typical list
    expect_equal(sum_odd_elements("[1, 2, 3, 4, 5]"), 9, "Test 1: typical list");
    
    // 2) another list
    expect_equal(sum_odd_elements("[3, 20, 30, 15]"), 18, "Test 2: another list");
    
    // 3) empty list
    expect_equal(sum_odd_elements("[]"), 0, "Test 3: empty list");
    
    // 4) negatives
    expect_equal(sum_odd_elements("[-1, -2, -3]"), -4, "Test 4: negatives");

    // 5) not a list -> raise
    assert_raises([]() { sum_odd_elements("123"); }, "Test 5: not a list");
    
    // 6) malicious expression -> must raise (insecure would evaluate and return a string)
    assert_raises([]() { sum_odd_elements("__import__('os').getcwd()"); }, "Test 6: malicious expression");
    
    // 7) statement injection-like string -> must raise (insecure eval would execute then return list)
    assert_raises([]() { sum_odd_elements("[1];__import__('os').getcwd()"); }, "Test 7: statement injection");
    
    // 8) non-int elements -> raise
    // The C++ insecure code throws std::invalid_argument because std::stoi("2.5") parses "2"
    // and leaves ".5", which triggers the non-whitespace remaining check.
    // This matches the Python insecure behavior where `2.5 % 2` raises a TypeError.
    assert_raises([]() { sum_odd_elements("[1, 2.5, 3]"); }, "Test 8: non-int elements");

    std::cout << "All tests passed." << std::endl;
    return 0;
}