#include <string>
#include <vector>
#include <unordered_map>
#include <stdexcept>
#include <iostream>
#include <cstdlib>
#include <functional>

int process_order(const std::vector<std::string>& products_list, const std::vector<int>& quantities_list) {
    const std::unordered_map<std::string, int> product_prices = {
        {"Laptop", 1000},
        {"Headphones", 500},
        {"Mouse", 50},
        {"Charger", 30}
    };
    const std::unordered_map<std::string, int> discounts = {
        {"Laptop", 100},
        {"Headphones", 50}
    };

    if (products_list.size() != quantities_list.size()) {
        throw std::invalid_argument("products_list and quantities_list must have the same length");
    }

    for (int q : quantities_list) {
        if (q < 0) {
            throw std::invalid_argument("quantities must be non-negative");
        }
    }

    int total_price = 0;
    for (size_t i = 0; i < products_list.size(); ++i) {
        const std::string& product = products_list[i];
        int quantity = quantities_list[i];

        auto price_it = product_prices.find(product);
        if (price_it != product_prices.end()) {
            int discount = 0;
            auto discount_it = discounts.find(product);
            if (discount_it != discounts.end()) {
                discount = discount_it->second;
            }
            total_price += (price_it->second - discount) * quantity;
        }
    }

    return total_price;
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

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still passes
    }
}

int main() {
    // Test 1: Standard order
    expect_equal(process_order({"Laptop", "Headphones", "Mouse"}, {2, 3, 1}), 3200, "Standard order test");

    // Test 2: Another standard order
    expect_equal(process_order({"Charger", "Mouse"}, {1, 1}), 80, "Charger and Mouse order test");

    // Test 3: Unknown product is ignored
    expect_equal(process_order({"Unknown", "Mouse"}, {10, 1}), 50, "Unknown product ignored test");

    // Test 4: Empty order
    expect_equal(process_order({}, {}), 0, "Empty order test");

    // Test 5: Mismatch length should raise
    assert_raises([]() {
        process_order({"Laptop", "Headphones", "Mouse"}, {2, 3});
    }, "Mismatch length test");

    // Test 6: Negative quantity should raise
    assert_raises([]() {
        process_order({"Mouse"}, {-1});
    }, "Negative quantity test");

    // Note: The Python tests for non-int quantity and non-list inputs cannot be directly translated 
    // to C++ because the C++ function signature strictly enforces types (std::vector<std::string> and std::vector<int>). 
    // Passing a double or a raw string literal instead of the vector is a compile-time error in C++, 
    // which inherently provides the type safety that the Python tests dynamically check for.

    std::cout << "All tests passed!" << std::endl;
    return 0;
}