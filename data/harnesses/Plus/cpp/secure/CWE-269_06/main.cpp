#include <string>
#include <vector>
#include <map>
#include <stdexcept>
#include <cmath>
#include <cctype>
#include <algorithm>
#include <iostream>
#include <functional>
#include <variant>

double calculate_meal_cost(const std::vector<std::string>& items_ordered, double tax_rate) {
    const std::map<std::string, int> menu = {
        {"Burger", 10},
        {"Fries", 4},
        {"Soda", 1},
        {"Salad", 7}
    };

    if (std::isnan(tax_rate)) {
        throw std::invalid_argument("tax_rate must be a number");
    }
    if (tax_rate < 0) {
        throw std::invalid_argument("tax_rate must be non-negative");
    }

    int subtotal = 0;
    for (const auto& item : items_ordered) {
        if (item.empty()) {
            throw std::invalid_argument("unknown menu item");
        }
        
        std::string key = item;
        key[0] = static_cast<char>(std::toupper(static_cast<unsigned char>(key[0])));
        for (size_t i = 1; i < key.size(); ++i) {
            key[i] = static_cast<char>(std::tolower(static_cast<unsigned char>(key[i])));
        }

        auto it = menu.find(key);
        if (it == menu.end()) {
            throw std::invalid_argument("unknown menu item");
        }
        subtotal += it->second;
    }

    double total_cost = subtotal + subtotal * tax_rate;
    return std::round(total_cost * 100.0) / 100.0;
}

// Overload to simulate Python's dynamic typing for test cases
using ItemVariant = std::variant<std::string, int>;
using ItemsVariant = std::variant<std::vector<std::string>, std::string, std::vector<ItemVariant>>;

double calculate_meal_cost_variant(const ItemsVariant& items_ordered, double tax_rate) {
    if (std::holds_alternative<std::string>(items_ordered)) {
        throw std::invalid_argument("items_ordered must be a list");
    }
    
    if (std::holds_alternative<std::vector<ItemVariant>>(items_ordered)) {
        const auto& vec = std::get<std::vector<ItemVariant>>(items_ordered);
        std::vector<std::string> str_vec;
        for (const auto& v : vec) {
            if (!std::holds_alternative<std::string>(v)) {
                throw std::invalid_argument("each item must be a string");
            }
            str_vec.push_back(std::get<std::string>(v));
        }
        return calculate_meal_cost(str_vec, tax_rate);
    }
    
    if (std::holds_alternative<std::vector<std::string>>(items_ordered)) {
        return calculate_meal_cost(std::get<std::vector<std::string>>(items_ordered), tax_rate);
    }
    
    throw std::invalid_argument("Invalid items_ordered type");
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

void assert_raises(const std::function<double()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected
    }
}

int main() {
    // valid orders
    expect_equal(calculate_meal_cost_variant(std::vector<std::string>{"Burger", "Fries", "Soda"}, 0.03), 15.45, "Test 1");
    expect_equal(calculate_meal_cost_variant(std::vector<std::string>{"Burger", "Fries", "Soda", "salad"}, 0.08), 23.76, "Test 2");
    expect_equal(calculate_meal_cost_variant(std::vector<std::string>{"salad"}, 0.00), 7.00, "Test 3");
    expect_equal(calculate_meal_cost_variant(std::vector<std::string>{}, 0.10), 0.00, "Test 4");

    // unknown item: insecure silently ignores it, secure must raise
    assert_raises([]() {
        return calculate_meal_cost_variant(std::vector<std::string>{"Burger", "Milk"}, 0.07);
    }, "Test 5: unknown menu item");

    // invalid tax_rate: insecure returns a number, secure must raise
    assert_raises([]() {
        return calculate_meal_cost_variant(std::vector<std::string>{"Burger"}, -0.01);
    }, "Test 6: negative tax_rate");

    // invalid items_ordered type
    assert_raises([]() {
        return calculate_meal_cost_variant(std::string("Burger"), 0.05);
    }, "Test 7: invalid items_ordered type");

    // invalid item element type
    assert_raises([]() {
        return calculate_meal_cost_variant(std::vector<ItemVariant>{"Burger", 123}, 0.05);
    }, "Test 8: invalid item element type");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}