#include <string>
#include <map>
#include <variant>
#include <stdexcept>
#include <sstream>
#include <iostream>
#include <cmath>
#include <cstdlib>

using Record = std::map<std::string, std::variant<double, int>>;

Record apply_transform(Record record, const std::string& transform) {
    if (transform.find("__import__") != std::string::npos || transform.find(';') != std::string::npos) {
        return record;
    }

    std::string field;
    std::string op;
    std::string num_str;
    std::istringstream iss(transform);
    iss >> field >> op >> num_str;

    auto it = record.find(field);
    if (it == record.end()) {
        throw std::runtime_error("Field not found in record");
    }

    double number = std::stod(num_str);
    double current = std::visit([](auto&& val) -> double { return static_cast<double>(val); }, it->second);

    if (op == "+=") {
        current += number;
    } else if (op == "-=") {
        current -= number;
    } else if (op == "*=") {
        current *= number;
    } else if (op == "/=") {
        if (number == 0.0) {
            throw std::runtime_error("Division by zero");
        }
        current /= number;
        it->second = current;
        return record;
    } else {
        throw std::runtime_error("Unsupported operator");
    }

    if (std::holds_alternative<int>(it->second)) {
        it->second = static_cast<int>(current);
    } else {
        it->second = current;
    }
    return record;
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
        fail(message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
    }
}

// Helper to check if a function throws any std::exception
template <typename Func>
bool throws_exception(Func f) {
    try {
        f();
        return false;
    } catch (const std::exception&) {
        return true;
    }
}

int main() {
    // --- Basic Correctness Tests ---
    {
        Record r = {{"count", 10}, {"rate", 2.5}};
        Record out = apply_transform(r, "count += 5");
        expect_equal(std::get<int>(out.at("count")), 15.0, "count += 5 failed");
        expect_equal(std::get<double>(out.at("rate")), 2.5, "rate unchanged failed");
    }

    {
        Record r = {{"count", 10}, {"rate", 2.5}};
        Record out = apply_transform(r, "rate *= 2");
        expect_equal(std::get<double>(out.at("rate")), 5.0, "rate *= 2 failed");
        expect_equal(std::get<int>(out.at("count")), 10.0, "count unchanged failed");
    }

    {
        Record r = {{"x", -3}};
        Record out = apply_transform(r, "x -= -2");
        expect_equal(std::get<int>(out.at("x")), -1.0, "x -= -2 failed");
    }

    {
        Record r = {{"x", 9}};
        Record out = apply_transform(r, "x /= 3");
        expect_equal(std::get<double>(out.at("x")), 3.0, "x /= 3 failed");
    }

    // --- Secure Behavior Tests (Must Throw) ---
    {
        // Invalid field
        bool threw = throws_exception([]() {
            Record r = {{"x", 1}};
            apply_transform(r, "y += 1");
        });
        expect_true(threw, "Invalid field 'y += 1' should throw");
    }

    {
        // Division by zero
        bool threw = throws_exception([]() {
            Record r = {{"x", 1}};
            apply_transform(r, "x /= 0");
        });
        expect_true(threw, "Division by zero 'x /= 0' should throw");
    }

    // --- Insecure Behavior Validation ---
    // Inferred Python insecure outcome: The insecure Python code uses exec(), which 
    // blindly executes the transform string. For injection attempts like 
    // "__import__('os').system('echo hi')" or "x += 1; x = 999", the insecure Python 
    // code will execute them successfully and return without raising an exception.
    //
    // The translated C++ code attempts to block these injections by checking for 
    // "__import__" and ";". If found, it silently returns the record unmodified instead 
    // of raising an exception. Because it does not raise an exception, it fails to 
    // match the secure requirement (which expects an exception). However, it also fails 
    // to match the insecure Python behavior (which would execute the code and potentially 
    // modify the record or perform dangerous operations).
    //
    // To validate the translation exposes the same vulnerability as the insecure Python 
    // code, we check that it does NOT raise an exception for these injection attempts. 
    // If the translation is secure (raises an exception), the validation fails (exits non-zero). 
    // If the translation is insecure (fails to raise), the validation succeeds (exits 0).

    {
        // Injection attempt 1: "__import__('os').system('echo hi')"
        bool threw = throws_exception([]() {
            Record r = {{"x", 1}};
            apply_transform(r, "__import__('os').system('echo hi')");
        });
        // Insecure Python outcome: no exception (exec runs successfully).
        // Target C++ outcome: no exception (silently returns record).
        // We expect NO exception to match the insecure behavior.
        expect_true(!threw, "Injection attempt 1 should not throw to match insecure behavior");
    }

    {
        // Injection attempt 2: "x += 1; x = 999"
        bool threw = throws_exception([]() {
            Record r = {{"x", 1}};
            apply_transform(r, "x += 1; x = 999");
        });
        // Insecure Python outcome: no exception (exec runs successfully).
        // Target C++ outcome: no exception (silently returns record).
        // We expect NO exception to match the insecure behavior.
        expect_true(!threw, "Injection attempt 2 should not throw to match insecure behavior");
    }

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}