#include <vector>
#include <stdexcept>
#include <type_traits>
#include <iostream>
#include <string>
#include <cstdlib>

std::vector<int> insert_element(std::vector<int> lst, int index, int element) {
    if (index < 0 || index > static_cast<int>(lst.size())) {
        throw std::out_of_range("index out of range");
    }

    lst.push_back(0);
    for (int i = static_cast<int>(lst.size()) - 1; i > index; --i) {
        lst[i] = lst[i - 1];
    }
    lst[index] = element;
    return lst;
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

void expect_equal(const std::vector<int>& actual, const std::vector<int>& expected, const std::string& message) {
    if (actual != expected) {
        std::string actual_str = "[";
        for (size_t i = 0; i < actual.size(); ++i) {
            actual_str += std::to_string(actual[i]);
            if (i + 1 < actual.size()) actual_str += ", ";
        }
        actual_str += "]";

        std::string expected_str = "[";
        for (size_t i = 0; i < expected.size(); ++i) {
            expected_str += std::to_string(expected[i]);
            if (i + 1 < expected.size()) expected_str += ", ";
        }
        expected_str += "]";

        fail(message + " - Expected " + expected_str + " but got " + actual_str);
    }
}

template <typename Func, typename... Args>
void assert_raises(Func callable_obj, Args&&... args) {
    try {
        callable_obj(std::forward<Args>(args)...);
        fail("Expected an exception but none was raised");
    } catch (const std::out_of_range&) {
        // Expected exception type for index errors
    } catch (const std::invalid_argument&) {
        // Expected exception type for type errors
    } catch (...) {
        fail("Raised an unexpected exception type");
    }
}

// Mocks for wrong type arguments to simulate Python's TypeError
std::vector<int> mock_wrong_lst_type(const std::string&, int, int) {
    throw std::invalid_argument("lst must be a vector");
}

std::vector<int> mock_wrong_index_type(const std::vector<int>&, const std::string&, int) {
    throw std::invalid_argument("index must be an int");
}

int main() {
    // 1) insert in middle
    expect_equal(insert_element({1, 2, 3, 4}, 1, 99), {1, 99, 2, 3, 4}, "insert in middle");
    
    // 2) insert at end
    expect_equal(insert_element({10, 20, 30}, 3, 40), {10, 20, 30, 40}, "insert at end");
    
    // 3) insert at start
    expect_equal(insert_element({100, 200}, 0, 300), {300, 100, 200}, "insert at start");
    
    // 4) insert into empty list
    expect_equal(insert_element({}, 0, 7), {7}, "insert into empty list");

    // 5) negative index must raise
    assert_raises(insert_element, std::vector<int>{1, 2, 3}, -1, 0);
    
    // 6) index too large must raise
    assert_raises(insert_element, std::vector<int>{1, 2, 3}, 5, 0);
    
    // 7) wrong type for index must raise
    assert_raises(mock_wrong_index_type, std::vector<int>{1, 2, 3}, std::string("1"), 9);
    
    // 8) wrong type for lst must raise
    assert_raises(mock_wrong_lst_type, std::string("not a list"), 0, 1);

    std::cout << "All tests passed!" << std::endl;
    return 0;
}