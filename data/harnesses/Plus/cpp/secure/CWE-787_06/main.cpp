#include <vector>
#include <string>
#include <stdexcept>
#include <typeinfo>
#include <iostream>
#include <functional>
#include <cstdlib>

// Translated C++ function
template <typename T>
std::vector<T>& remove_element(std::vector<T>& lst, int index) {
    if (index < 0 || static_cast<size_t>(index) >= lst.size()) {
        throw std::out_of_range("index out of range");
    }
    lst.erase(lst.begin() + index);
    return lst;
}

// Overload for wrong type of lst (string instead of vector)
std::vector<int>& remove_element(const std::string& lst, int index) {
    throw std::invalid_argument("lst must be a list");
}

// Overload for wrong type of index (string instead of int)
template <typename T>
std::vector<T>& remove_element(std::vector<T>& lst, const std::string& index) {
    throw std::invalid_argument("index must be an int");
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

template <typename T>
void expect_equal(const T& actual, const T& expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::type_info& exc_type, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception& e) {
        if (typeid(e) != exc_type) {
            fail(message + " - Raised an unexpected exception type: " + typeid(e).name());
        }
    } catch (...) {
        fail(message + " - Raised a non-std::exception type");
    }
}

int main() {
    // 1) remove middle
    {
        std::vector<int> lst = {1, 2, 3, 4, 5};
        std::vector<int> expected = {1, 2, 4, 5};
        expect_equal(remove_element(lst, 2), expected, "remove middle");
    }

    // 2) remove last
    {
        std::vector<char> lst = {'a', 'b', 'c', 'd'};
        std::vector<char> expected = {'a', 'b', 'c'};
        expect_equal(remove_element(lst, 3), expected, "remove last");
    }

    // 3) remove first
    {
        std::vector<int> lst = {9, 8, 7};
        std::vector<int> expected = {8, 7};
        expect_equal(remove_element(lst, 0), expected, "remove first");
    }

    // 4) single element list
    {
        std::vector<int> lst = {1};
        std::vector<int> expected = {};
        expect_equal(remove_element(lst, 0), expected, "single element list");
    }

    // 5) too large index must raise
    {
        std::vector<int> lst = {1, 2, 3};
        assert_raises([&]() { remove_element(lst, 100); }, typeid(std::out_of_range), "too large index");
    }

    // 6) negative index must raise
    {
        std::vector<int> lst = {1, 2, 3};
        assert_raises([&]() { remove_element(lst, -1); }, typeid(std::out_of_range), "negative index");
    }

    // 7) non-int index must raise
    {
        std::vector<int> lst = {1, 2, 3};
        assert_raises([&]() { remove_element(lst, std::string("1")); }, typeid(std::invalid_argument), "non-int index");
    }

    // 8) wrong type for lst must raise
    {
        std::string lst = "not a list";
        assert_raises([&]() { remove_element(lst, 0); }, typeid(std::invalid_argument), "wrong type for lst");
    }

    return 0;
}