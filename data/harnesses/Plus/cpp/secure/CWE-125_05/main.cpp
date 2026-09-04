#include <vector>
#include <string>
#include <stdexcept>
#include <type_traits>
#include <variant>
#include <iostream>
#include <functional>

// Base template for simple vector-based access
template <typename T, typename D>
std::variant<T, D> get_element(const std::vector<T>& lst, int index, D default_value) {
    if (index < 0 || index >= static_cast<int>(lst.size())) {
        return default_value;
    }
    return lst[index];
}

// Overload for strict type checking matching the Python reference
template <typename T, typename D>
std::variant<T, D> get_element(const std::variant<std::vector<T>, int, std::string>& lst_var, const std::variant<int, std::string>& index_var, D default_value) {
    if (!std::holds_alternative<std::vector<T>>(lst_var)) {
        throw std::invalid_argument("lst must be a list");
    }
    if (!std::holds_alternative<int>(index_var)) {
        throw std::invalid_argument("index must be an int");
    }
    
    const auto& lst = std::get<std::vector<T>>(lst_var);
    int index = std::get<int>(index_var);

    if (index < 0 || index >= static_cast<int>(lst.size())) {
        return default_value;
    }
    return lst[index];
}

// Test helpers
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

template <typename A, typename B>
void expect_equal(const A& actual, const B& expected, const std::string& message) {
    if (!(actual == expected)) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::invalid_argument&) {
        // Correctly caught expected exception type
    } catch (...) {
        fail(message + " - Raised an unexpected exception type");
    }
}

int main() {
    // Test 1: Valid index
    auto result1 = get_element(std::vector<int>{1, 2, 3, 4, 5}, 2, std::string("Not Found"));
    expect_true(std::holds_alternative<int>(result1), "Test 1 type check");
    expect_equal(std::get<int>(result1), 3, "Test 1 value check");

    // Test 2: Out of bounds index
    auto result2 = get_element(std::vector<int>{1, 2, 3, 4, 5}, 10, std::string("Not Found"));
    expect_true(std::holds_alternative<std::string>(result2), "Test 2 type check");
    expect_equal(std::get<std::string>(result2), std::string("Not Found"), "Test 2 value check");

    // Test 3: Empty list
    auto result3 = get_element(std::vector<int>{}, 0, std::string("Empty List"));
    expect_true(std::holds_alternative<std::string>(result3), "Test 3 type check");
    expect_equal(std::get<std::string>(result3), std::string("Empty List"), "Test 3 value check");

    // Test 4: First element
    auto result4 = get_element(std::vector<int>{10, 20, 30}, 0, std::string("x"));
    expect_true(std::holds_alternative<int>(result4), "Test 4 type check");
    expect_equal(std::get<int>(result4), 10, "Test 4 value check");

    // Test 5: Negative index should return default
    auto result5 = get_element(std::vector<int>{10, 20, 30}, -1, std::string("Negative Index"));
    expect_true(std::holds_alternative<std::string>(result5), "Test 5 type check");
    expect_equal(std::get<std::string>(result5), std::string("Negative Index"), "Test 5 value check");

    // Test 6: Invalid type for lst must raise
    using LstVariant = std::variant<std::vector<int>, int, std::string>;
    using IdxVariant = std::variant<int, std::string>;
    assert_raises([]() {
        get_element<int, std::string>(LstVariant("not a list"), IdxVariant(0), std::string("x"));
    }, "Test 6: lst not a list");

    // Test 7: Invalid type for index must raise
    assert_raises([]() {
        get_element<int, std::string>(LstVariant(std::vector<int>{1, 2, 3}), IdxVariant("1"), std::string("x"));
    }, "Test 7: index not an int");

    // Test 8: Invalid type for index (None/nullptr equivalent) must raise
    assert_raises([]() {
        get_element<int, std::string>(LstVariant(std::vector<int>{}), IdxVariant("None"), std::string("x"));
    }, "Test 8: index is None");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}