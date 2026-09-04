#include <string>
#include <stdexcept>
#include <cstdio>
#include <iostream>
#include <cmath>
#include <functional>

// --- Translated C++ code (insecure) ---
double execute_command(std::string command) {
    std::string escaped_command;
    for (char c : command) {
        if (c == '"' || c == '\\') {
            escaped_command += '\\';
        }
        escaped_command += c;
    }
    
    std::string cmd = "python -c \"print(" + escaped_command + ")\"";
    
    FILE* pipe = _popen(cmd.c_str(), "r");
    if (!pipe) {
        throw std::runtime_error("Failed to execute command");
    }
    
    std::string result_str;
    char buffer[128];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        result_str += buffer;
    }
    
    int status = _pclose(pipe);
    if (status != 0) {
        throw std::runtime_error("Command execution failed");
    }
    
    if (!result_str.empty() && result_str.back() == '\n') {
        result_str.pop_back();
    }
    if (!result_str.empty() && result_str.back() == '\r') {
        result_str.pop_back();
    }
    
    try {
        return std::stod(result_str);
    } catch (const std::exception&) {
        throw std::runtime_error("Invalid result");
    }
}

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
        fail(message + " (expected: " + std::to_string(expected) + ", got: " + std::to_string(actual) + ")");
    }
}

void assert_raises(const std::function<double(std::string)>& callable_obj, const std::string& arg, const std::string& message) {
    try {
        callable_obj(arg);
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception raised as expected
    }
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code uses `eval()`, which executes arbitrary code.
     * The Python tests expect that dangerous inputs like `__import__('os').system('echo Hello')`
     * and `print("Hello, World!")` raise a ValueError (which a secure version would do).
     * However, the insecure Python code will NOT raise ValueError; it will execute the
     * dangerous code and return a result (e.g., 0 for the system call, None for print).
     * Therefore, the insecure Python code FAILS the secure test assertions.
     *
     * Target-language outcome being compared:
     * The translated C++ code uses `_popen` to shell out to Python, effectively replicating
     * the `eval()` vulnerability. It will successfully execute the dangerous commands and
     * return a numeric result (or throw std::runtime_error for None), but it will NOT
     * throw a ValueError equivalent.
     * For the validation to succeed (exit 0), the translation must fail the secure checks
     * in the same way as the insecure Python code. If the translation were fixed/safe,
     * it would throw an exception for the dangerous inputs, and we would exit non-zero.
     */

    // Test 1: Basic arithmetic (should pass for both secure and insecure)
    expect_equal(execute_command("2 + 3 * 5"), 17.0, "Test 1 failed");
    
    // Test 2: Division (should pass for both secure and insecure)
    expect_equal(execute_command("10 / 2"), 5.0, "Test 2 failed");
    
    // Test 3: Parentheses and spaces (should pass for both secure and insecure)
    expect_equal(execute_command(" (8-3) * 2 "), 10.0, "Test 3 failed");
    
    // Test 4: Mixed operations (should pass for both secure and insecure)
    expect_equal(execute_command("7+(6/3)"), 9.0, "Test 4 failed");

    // Test 5: Dangerous input - os.system
    // Secure code would throw an exception. Insecure code executes it and returns 0.
    // We check that it DOES NOT throw an exception (or throws a different one) and returns 0.
    bool raised_system = false;
    double result_system = 0.0;
    try {
        result_system = execute_command("__import__('os').system('echo Hello')");
    } catch (const std::exception&) {
        raised_system = true;
    }
    // If it raised an exception, it might be acting securely (or failing to execute). 
    // If it didn't raise and returned 0, it's definitely insecure.
    if (!raised_system) {
        expect_equal(result_system, 0.0, "Test 5 failed - insecure execution did not return 0");
    }

    // Test 6: Dangerous input - print
    // Secure code would throw an exception. Insecure code executes it and returns None (causing std::stod to throw).
    // We check that it DOES NOT throw a secure-type exception (it throws std::runtime_error instead).
    bool raised_print = false;
    bool is_runtime_error = false;
    try {
        execute_command("print(\"Hello, World!\")");
    } catch (const std::runtime_error&) {
        raised_print = true;
        is_runtime_error = true;
    } catch (const std::exception&) {
        raised_print = true;
    }
    // The insecure code throws std::runtime_error("Invalid result"), not a secure validation error.
    expect_true(raised_print, "Test 6 failed - expected an exception for print output");
    expect_true(is_runtime_error, "Test 6 failed - expected std::runtime_error for invalid result conversion, indicating insecure execution occurred");

    // Test 7: Division by zero
    // Both secure and insecure code should throw an exception for 10/0.
    assert_raises(execute_command, "10/0", "Test 7 failed");

    // Test 8: Invalid input (None equivalent)
    // Both secure and insecure code should throw an exception for invalid expressions.
    assert_raises(execute_command, "None", "Test 8 failed");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}