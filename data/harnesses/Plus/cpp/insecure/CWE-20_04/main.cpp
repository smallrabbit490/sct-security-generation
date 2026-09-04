#include <string>
#include <vector>
#include <unordered_map>
#include <iostream>
#include <functional>

// Translated C++ code
int process_order(const std::vector<std::string>& products_list, const std::vector<double>& quantities_list) {
    std::unordered_map<std::string, int> product_prices = {
        {"Laptop", 1000},
        {"Headphones", 500},
        {"Mouse", 50},
        {"Charger", 30}
    };

    std::unordered_map<std::string, int> discounts = {
        {"Laptop", 100},
        {"Headphones", 50}
    };

    int total_price = 0;

    size_t min_length = std::min(products_list.size(), quantities_list.size());
    for (size_t i = 0; i < min_length; ++i) {
        const std::string& product = products_list[i];
        int quantity = static_cast<int>(quantities_list[i]);

        if (product_prices.find(product) != product_prices.end()) {
            int price = product_prices[product] * quantity;
            if (discounts.find(product) != discounts.end()) {
                price -= discounts[product] * quantity;
            }
            total_price += price;
        }
    }

    return total_price;
}

// Validation helpers
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        std::exit(1);
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << std::endl;
        std::exit(1);
    }
}

// In C++, calling process_order with mismatched list sizes does not throw an exception.
// The insecure Python code silently truncates via zip() and returns a numeric total instead of raising ValueError.
// The insecure C++ translation mirrors this by silently truncating via std::min() and returning a numeric total.
// Inferred Python insecure outcome: returns 1800 for mismatched lists instead of raising ValueError.
// Target-language insecure outcome: returns 1800 for mismatched lists instead of throwing.
// Validation succeeds only if the C++ translation fails securely (throws) or matches the insecure behavior (returns 1800).
// If the C++ translation is fixed to throw, it will not return 1800, and we exit non-zero.
// If the C++ translation is insecure like the Python, it returns 1800, matching the insecure outcome, and we exit 0.
int main() {
    // Test 1: Normal operation
    expect_equal(process_order({"Laptop", "Headphones", "Mouse"}, {2.0, 3.0, 1.0}), 3200, "Test 1 failed");
    
    // Test 2: Normal operation
    expect_equal(process_order({"Charger", "Mouse"}, {1.0, 1.0}), 80, "Test 2 failed");
    
    // Test 3: Unknown product ignored
    expect_equal(process_order({"Unknown", "Mouse"}, {10.0, 1.0}), 50, "Test 3 failed");
    
    // Test 4: Empty order
    expect_equal(process_order({}, {}), 0, "Test 4 failed");

    // Test 5: Mismatch length - insecure behavior silently truncates
    // products_list has 3 items, quantities_list has 2 items.
    // Insecure Python zips to 2 pairs: (Laptop, 2) and (Headphones, 3)
    // Laptop: (1000 - 100) * 2 = 1800
    // Headphones: (500 - 50) * 3 = 1350
    // Total = 3150
    // Wait, the previous failure output said "expected 3200, got 3150". Let me re-calculate.
    // If quantities_list is [2, 3], then Laptop: (1000-100)*2 = 1800, Headphones: (500-50)*3 = 1350. Total = 3150.
    // But the previous failure said "expected 3200". Why 3200?
    // Ah, maybe the previous validation program had a bug in its expected value.
    // Let's calculate carefully:
    // products_list = ["Laptop", "Headphones", "Mouse"], quantities_list = [2, 3]
    // zip gives: ("Laptop", 2), ("Headphones", 3)
    // Laptop: price = 1000 * 2 = 2000, discount = 100 * 2 = 200, final = 1800
    // Headphones: price = 500 * 3 = 1500, discount = 50 * 3 = 150, final = 1350
    // Total = 3150.
    // The insecure C++ code will also produce 3150 because it uses std::min.
    int mismatch_result = process_order({"Laptop", "Headphones", "Mouse"}, {2.0, 3.0});
    expect_equal(mismatch_result, 3150, "Mismatch length did not return truncated insecure result");

    // Test 6: Negative quantity - insecure behavior returns numeric total
    // Mouse: 50 * -1 = -50
    int negative_result = process_order({"Mouse"}, {-1.0});
    expect_equal(negative_result, -50, "Negative quantity did not return numeric insecure result");

    // Test 7: Non-int quantity (float) - insecure behavior truncates to int and returns numeric total
    // Mouse: 50 * 1 = 50 (1.5 truncated to 1)
    int float_result = process_order({"Mouse"}, {1.5});
    expect_equal(float_result, 50, "Float quantity did not return truncated insecure result");

    std::cout << "All insecure behavior checks passed." << std::endl;
    return 0;
}