#include <vector>
#include <stdexcept>
#include <type_traits>
#include <utility>
#include <iostream>
#include <functional>
#include <string>

template <typename T>
std::vector<T>& swap_segments(std::vector<T>& buf, int a_start, int b_start, int seg_len) {
    if (seg_len <= 0) {
        throw std::invalid_argument("seg_len must be positive");
    }

    int n = static_cast<int>(buf.size());
    if (a_start < 0 || b_start < 0) {
        throw std::out_of_range("start indices out of range");
    }
    if (a_start + seg_len > n || b_start + seg_len > n) {
        throw std::out_of_range("segment exceeds buffer bounds");
    }

    int a0 = a_start;
    int a1 = a_start + seg_len;
    int b0 = b_start;
    int b1 = b_start + seg_len;

    if (!(a1 <= b0 || b1 <= a0)) {
        throw std::invalid_argument("segments overlap");
    }

    for (int i = 0; i < seg_len; ++i) {
        std::swap(buf[a_start + i], buf[b_start + i]);
    }

    return buf;
}

// Test helpers
int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
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

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raising
    }
}

// Wrapper to test the template with int
void test_swap_int(std::vector<int>& buf, int a_start, int b_start, int seg_len) {
    swap_segments(buf, a_start, b_start, seg_len);
}

// Wrapper to test the template with std::string
void test_swap_str(std::vector<std::string>& buf, int a_start, int b_start, int seg_len) {
    swap_segments(buf, a_start, b_start, seg_len);
}

int main() {
    // 1) normal swap
    {
        std::vector<int> buf = {1, 2, 3, 4, 5, 6};
        swap_segments(buf, 0, 3, 2);
        expect_equal(buf, std::vector<int>{4, 5, 3, 1, 2, 6}, "Test 1: normal swap");
    }

    // 2) another swap
    {
        std::vector<std::string> buf = {"a", "b", "c", "d"};
        swap_segments(buf, 0, 2, 2);
        expect_equal(buf, std::vector<std::string>{"c", "d", "a", "b"}, "Test 2: another swap");
    }

    // 3) swap single element segments
    {
        std::vector<int> buf = {9, 8, 7};
        swap_segments(buf, 0, 2, 1);
        expect_equal(buf, std::vector<int>{7, 8, 9}, "Test 3: single element swap");
    }

    // 4) out-of-bounds segment must raise (insecure may partially modify then crash)
    {
        std::vector<int> buf = {1, 2, 3};
        assert_raises([&]() { test_swap_int(buf, 2, 0, 2); }, "Test 4: out-of-bounds segment");
    }

    // 5) negative start must raise (insecure would swap using negative indexing)
    {
        std::vector<int> buf = {1, 2, 3};
        assert_raises([&]() { test_swap_int(buf, -1, 1, 1); }, "Test 5: negative start index");
    }

    // 6) overlapping segments must raise
    {
        std::vector<int> buf = {1, 2, 3, 4};
        assert_raises([&]() { test_swap_int(buf, 1, 2, 2); }, "Test 6: overlapping segments");
    }

    // 7) seg_len invalid must raise
    {
        std::vector<int> buf = {1, 2};
        assert_raises([&]() { test_swap_int(buf, 0, 1, 0); }, "Test 7: seg_len zero");
    }

    // 8) seg_len negative must raise
    {
        std::vector<int> buf = {1, 2};
        assert_raises([&]() { test_swap_int(buf, 0, 1, -1); }, "Test 8: seg_len negative");
    }

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}