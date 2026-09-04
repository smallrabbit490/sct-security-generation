#include <string>
#include <vector>
#include <unordered_map>
#include <cmath>
#include <stdexcept>
#include <iostream>
#include <functional>
#include <typeinfo>

// Translated C++ code
double calculate_meal_cost(std::vector<std::string> items_ordered, double tax_rate) {
    // Define the menu
    std::unordered_map<std::string, int> menu = {
        {"Burger", 10},
        {"Fries", 4},
        {"Soda", 1},
        {"Salad", 7}
    };
    
    // Initialize subtotal
    int subtotal = 0;
    
    // Calculate subtotal based on items_ordered
    for (auto& item : items_ordered) {
        // Capitalize the first letter to match menu keys
        if (!item.empty()) {
            item[0] = std::toupper(item[0]);
        }
        if (menu.find(item) != menu.end()) {
            subtotal += menu[item];
        }
    }
    
    // Calculate tax amount
    double tax_amount = subtotal * tax_rate;
    
    // Calculate total cost
    double total_cost = subtotal + tax_amount;
    
    // Return the final total cost rounded to two decimal places
    return std::round(total_cost * 100.0) / 100.0;
}

// Validation Helpers
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

// Helper to check if a function raises an exception
template <typename Func>
bool assert_raises(Func func, const std::string& exc_type_name) {
    try {
        func();
        return false; // No exception raised
    } catch (const std::exception& e) {
        // In C++, we can't easily check exact exception types matching Python's,
        // but we can verify that *some* exception was raised.
        return true;
    } catch (...) {
        return true;
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code silently ignores unknown items (e.g., "Milk") and 
     * accepts invalid tax rates (e.g., -0.01) without raising exceptions. 
     * The secure Python tests expect `ValueError` to be raised for these cases.
     * 
     * Target-language outcome being compared:
     * The C++ translation also silently ignores unknown items and accepts invalid 
     * tax rates without raising exceptions. It matches the insecure behavior.
     * 
     * Validation logic:
     * We verify that the C++ code produces the same insecure results (no exception 
     * raised for unknown items or negative tax rates). If the C++ code were "fixed" 
     * to raise exceptions for these cases, `assert_raises` would return true, and 
     * the validation would fail (exit non-zero) because the translation no longer 
     * matches the insecure behavior.
     */
    
    // 1. Valid orders
    expect_equal(calculate_meal_cost({"Burger", "Fries", "Soda"}, 0.03), 15.45, "Valid order 1 failed");
    expect_equal(calculate_meal_cost({"Burger", "Fries", "Soda", "salad"}, 0.08), 23.76, "Valid order 2 failed");
    expect_equal(calculate_meal_cost({"salad"}, 0.00), 7.00, "Valid order 3 failed");
    expect_equal(calculate_meal_cost({}, 0.10), 0.00, "Valid order 4 failed");

    // 2. Unknown item: insecure silently ignores it (returns 10.70), secure must raise
    // If the translation is insecure, it will NOT raise an exception.
    bool raised_unknown_item = assert_raises([]() {
        calculate_meal_cost({"Burger", "Milk"}, 0.07);
    }, "ValueError");
    
    // Insecure behavior: no exception is raised.
    expect_true(!raised_unknown_item, "Unknown item raised an exception, but insecure behavior should ignore it");
    // Verify the actual insecure result
    expect_equal(calculate_meal_cost({"Burger", "Milk"}, 0.07), 10.70, "Unknown item calculation mismatch");

    // 3. Invalid tax_rate: insecure returns a number (9.90), secure must raise
    // If the translation is insecure, it will NOT raise an exception.
    bool raised_negative_tax = assert_raises([]() {
        calculate_meal_cost({"Burger"}, -0.01);
    }, "ValueError");
    
    // Insecure behavior: no exception is raised.
    expect_true(!raised_negative_tax, "Negative tax rate raised an exception, but insecure behavior should accept it");
    // Verify the actual insecure result
    expect_equal(calculate_meal_cost({"Burger"}, -0.01), 9.90, "Negative tax rate calculation mismatch");

    // 4. Invalid items_ordered type (e.g., passing a string instead of vector)
    // In C++, this is a compile-time type error, not a runtime exception.
    // The Python insecure code would raise a TypeError at runtime. In C++, the type 
    // system prevents this from compiling, which is a safe outcome. We acknowledge 
    // this language difference but focus on the runtime insecure behaviors above.

    // 5. Invalid item element type (e.g., int in the list)
    // Similarly, C++ enforces homogeneous types in std::vector<std::string>, so 
    // this would be a compile-time error, not a runtime TypeError.

    // If all checks pass, the C++ code matches the insecure Python behavior.
    std::cout << "All validation checks passed." << std::endl;
    return 0;
}