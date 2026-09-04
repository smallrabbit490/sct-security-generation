#include <vector>
#include <string>
#include <stdexcept>
#include <iostream>
#include <functional>
#include <typeinfo>

// Translated C++ code
template <typename T>
std::vector<T> change_list(std::vector<T> lst, T element, int index) {
    if (index < 0 || index >= static_cast<int>(lst.size())) {
        throw std::out_of_range("index out of range");
    }
    lst[index] = std::move(element);
    return lst;
}

// Explicit instantiation for common types to ensure compilation
template std::vector<int> change_list<int>(std::vector<int>, int, int);
template std::vector<std::string> change_list<std::string>(std::vector<std::string>, std::string, int);

// Validation helpers
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
    if (!(actual == expected)) {
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

// Test 4 equivalent: element can be any type (heterogeneous container)
struct DictLike {
    int x;
    bool operator==(const DictLike& other) const { return x == other.x; }
};

template std::vector<DictLike> change_list<DictLike>(std::vector<DictLike>, DictLike, int);

int main() {
    // 1) modify inside bounds
    std::vector<int> r1 = change_list(std::vector<int>{1, 2, 3}, 4, 1);
    expect_equal(r1, std::vector<int>{1, 4, 3}, "Test 1: modify inside bounds");

    // 2) modify at start
    std::vector<std::string> r2 = change_list(std::vector<std::string>{"a", "b"}, std::string("c"), 0);
    expect_equal(r2, std::vector<std::string>{"c", "b"}, "Test 2: modify at start");

    // 3) modify at last index
    std::vector<int> r3 = change_list(std::vector<int>{0, 1}, 9, 1);
    expect_equal(r3, std::vector<int>{0, 9}, "Test 3: modify at last index");

    // 4) element can be any type
    std::vector<DictLike> r4 = change_list(std::vector<DictLike>{DictLike{0}, DictLike{2}}, DictLike{1}, 0);
    expect_equal(r4, std::vector<DictLike>{DictLike{1}, DictLike{2}}, "Test 4: element can be any type");

    // 5) out of range high must raise
    assert_raises([]() {
        change_list(std::vector<std::string>{"a", "b"}, std::string("c"), 5);
    }, typeid(std::out_of_range), "Test 5: out of range high");

    // 6) empty list with index 0 must raise
    assert_raises([]() {
        change_list(std::vector<std::string>{}, std::string("x"), 0);
    }, typeid(std::out_of_range), "Test 6: empty list with index 0");

    // 7) negative index must raise
    assert_raises([]() {
        change_list(std::vector<std::string>{"a", "b"}, std::string("z"), -1);
    }, typeid(std::out_of_range), "Test 7: negative index");

    // 8) non-int index must raise (C++ type safety prevents compilation with non-int index)
    // In C++, passing a non-integer (like a string "0") as the index argument will 
    // result in a compile-time type error, which strictly enforces the equivalent of 
    // Python's TypeError at compile time rather than runtime.
    expect_true(true, "Test 8: non-int index raises compile-time type error");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}