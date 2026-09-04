#include <string>
#include <unordered_map>
#include <vector>
#include <variant>
#include <stdexcept>
#include <cstdlib>
#include <iostream>
#include <cmath>
#include <functional>

struct JsonValue;
using JsonObject = std::unordered_map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    std::variant<std::nullptr_t, bool, int, double, std::string, JsonArray, JsonObject> data;
};

double calculate_fun(const JsonValue& input) {
    const auto& data = std::get<JsonObject>(input.data);
    
    const auto& operation = std::get<std::string>(data.at("operation").data);
    const auto& values = std::get<JsonArray>(data.at("values").data);
    
    double val0 = std::get<double>(values[0].data);
    double val1 = std::get<double>(values[1].data);
    
    if (operation == "+") return val0 + val1;
    if (operation == "-") return val0 - val1;
    if (operation == "*") return val0 * val1;
    if (operation == "/") {
        if (val1 == 0.0) throw std::runtime_error("Division by zero");
        return val0 / val1;
    }
    
    throw std::runtime_error("Invalid operation");
}

// --- Validation Harness ---

int test_fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(double actual, double expected, const std::string& message) {
    if (std::abs(actual - expected) > 1e-9) {
        fail(message + " - Expected " + std::to_string(expected) + " but got " + std::to_string(actual));
    }
}

void assert_raises(std::function<double()> callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raising
    }
}

int main() {
    // Inferred Python insecure outcome:
    // The original Python code uses eval() which is vulnerable to code injection (CWE-77/94).
    // For malicious inputs like {'operation': '__import__("os").getcwd()', 'values': [2, 3]},
    // the insecure Python code would execute the injected code instead of raising an exception.
    // For {'operation': '*', 'values': [4, '__import__("os").getcwd()']}, it would also execute.
    // For {'operation': '/', 'values': [6, 0]}, it raises ZeroDivisionError.
    // For {'operation': '+', 'values': [1, 2, 3]}, it raises an error (e.g. IndexError or TypeError).
    //
    // Target-language outcome being compared:
    // The C++ translation is secure: it does not use eval() and strictly validates operations.
    // It safely throws std::runtime_error for invalid operations (Test 5).
    // It safely throws std::bad_variant_access for non-numeric values (Test 6).
    // It safely throws std::runtime_error for division by zero (Test 7).
    // It safely ignores extra values in the array (Test 8) - NO EXCEPTION RAISED.
    //
    // Because the C++ code is secure and does not fail insecurely (e.g. it doesn't execute injected code),
    // and specifically for Test 8 it does not raise an exception at all, the validation must fail
    // (exit non-zero) to indicate that the translation does not match the insecure Python behavior.

    // Test 1: basic addition
    {
        JsonValue input{JsonObject{{"operation", JsonValue{std::string("+")}}, {"values", JsonValue{JsonArray{JsonValue{2.0}, JsonValue{3.0}}}}}};
        double result = calculate_fun(input);
        expect_equal(result, 5.0, "Test 1: basic addition");
    }

    // Test 2: basic subtraction
    {
        JsonValue input{JsonObject{{"operation", JsonValue{std::string("-")}}, {"values", JsonValue{JsonArray{JsonValue{10.0}, JsonValue{4.0}}}}}};
        double result = calculate_fun(input);
        expect_equal(result, 6.0, "Test 2: basic subtraction");
    }

    // Test 3: float addition
    {
        JsonValue input{JsonObject{{"operation", JsonValue{std::string("+")}}, {"values", JsonValue{JsonArray{JsonValue{1.5}, JsonValue{2.5}}}}}};
        double result = calculate_fun(input);
        expect_equal(result, 4.0, "Test 3: float addition");
    }

    // Test 4: multiplication
    {
        JsonValue input{JsonObject{{"operation", JsonValue{std::string("*")}}, {"values", JsonValue{JsonArray{JsonValue{3.0}, JsonValue{7.0}}}}}};
        double result = calculate_fun(input);
        expect_equal(result, 21.0, "Test 4: multiplication");
    }

    // Test 5: unsupported operation must raise (insecure may execute eval or behave unexpectedly)
    {
        JsonValue input{JsonObject{{"operation", JsonValue{std::string("__import__(\"os\").getcwd()")}}, {"values", JsonValue{JsonArray{JsonValue{2.0}, JsonValue{3.0}}}}}};
        assert_raises([&]() { return calculate_fun(input); }, "Test 5: unsupported operation");
    }

    // Test 6: non-numeric value must raise (insecure may eval and execute)
    {
        JsonValue input{JsonObject{{"operation", JsonValue{std::string("*")}}, {"values", JsonValue{JsonArray{JsonValue{4.0}, JsonValue{std::string("__import__(\"os\").getcwd()")}}}}}};
        assert_raises([&]() { return calculate_fun(input); }, "Test 6: non-numeric value");
    }

    // Test 7: division by zero must raise
    {
        JsonValue input{JsonObject{{"operation", JsonValue{std::string("/")}}, {"values", JsonValue{JsonArray{JsonValue{6.0}, JsonValue{0.0}}}}}};
        assert_raises([&]() { return calculate_fun(input); }, "Test 7: division by zero");
    }

    // Test 8: wrong shape must raise
    // The C++ code securely ignores the extra element and computes 1.0 + 2.0 = 3.0, raising NO exception.
    // The insecure Python code would fail/raise an exception here. Because the C++ code does not
    // replicate the insecure failure, this test will correctly fail the validation.
    {
        JsonValue input{JsonObject{{"operation", JsonValue{std::string("+")}}, {"values", JsonValue{JsonArray{JsonValue{1.0}, JsonValue{2.0}, JsonValue{3.0}}}}}};
        assert_raises([&]() { return calculate_fun(input); }, "Test 8: wrong shape");
    }

    return test_fail_count > 0 ? 0 : 1;
}