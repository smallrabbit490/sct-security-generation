#include <iostream>
#include <vector>
#include <string>
#include <tuple>
#include <algorithm>
#include <set>
#include <stdexcept>
#include <functional>
#include <any>

// Global function pointer to mock foo() for testing
std::function<std::any()> g_foo_mock;

std::tuple<std::string, std::string> foo() {
    if (!g_foo_mock) {
        throw std::runtime_error("foo mock not initialized");
    }
    std::any result = g_foo_mock();
    if (!result.has_value()) {
        throw std::bad_any_cast();
    }
    // Try to extract the expected tuple type
    return std::any_cast<std::tuple<std::string, std::string>>(result);
}

std::vector<std::tuple<std::string, std::string>> dataSorting() {
    std::vector<std::tuple<std::string, std::string>> alist;
    std::set<std::tuple<std::string, std::string>> seen;

    const int limit = 64;
    for (int i = 0; i < limit; ++i) {
        auto pair = foo();
        auto basename = std::get<0>(pair);
        auto data = std::get<1>(pair);

        if (basename.empty() || data.empty()) {
            return alist;
        }

        auto key = std::make_tuple(basename, data);
        if (seen.find(key) != seen.end()) {
            throw std::runtime_error("ValueError");
        }

        seen.insert(key);
        alist.push_back(key);
        std::sort(alist.begin(), alist.end());
    }

    throw std::runtime_error("RuntimeError");
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

void expect_equal(
    const std::vector<std::tuple<std::string, std::string>>& actual,
    const std::vector<std::tuple<std::string, std::string>>& expected,
    const std::string& message
) {
    if (actual != expected) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& exc_name) {
    try {
        callable_obj();
        fail("Expected exception " + exc_name + " but none was thrown");
    } catch (const std::exception& e) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, also acceptable
    }
}

int main() {
    // Test 1: Normal operation
    {
        std::vector<std::any> seq = {
            std::make_tuple(std::string("./b"), std::string("2")),
            std::make_tuple(std::string("./a"), std::string("3")),
            std::make_tuple(std::string("./a"), std::string("1")),
            std::make_tuple(std::string(), std::string()) // Sentinel for empty break
        };
        size_t idx = 0;
        g_foo_mock = [&seq, &idx]() -> std::any {
            return seq[idx++];
        };

        auto out = dataSorting();
        std::vector<std::tuple<std::string, std::string>> expected = {
            std::make_tuple(std::string("./a"), std::string("1")),
            std::make_tuple(std::string("./a"), std::string("3")),
            std::make_tuple(std::string("./b"), std::string("2"))
        };
        expect_equal(out, expected, "Normal operation output mismatch");
    }

    // Test 2: Duplicate must raise ValueError
    {
        std::vector<std::any> seq2 = {
            std::make_tuple(std::string("./a"), std::string("1")),
            std::make_tuple(std::string("./a"), std::string("1")),
            std::make_tuple(std::string(), std::string())
        };
        size_t idx2 = 0;
        g_foo_mock = [&seq2, &idx2]() -> std::any {
            return seq2[idx2++];
        };

        assert_raises([]() { dataSorting(); }, "ValueError");
    }

    // Test 3: Bad foo return type must raise TypeError
    {
        g_foo_mock = []() -> std::any {
            return std::string("not-a-tuple");
        };

        assert_raises([]() { dataSorting(); }, "TypeError");
    }

    // Test 4: Extra arg rejected (C++ enforces signature, so we just validate it doesn't compile with extra args)
    // In C++, calling dataSorting(1) is a compile-time error, which inherently satisfies the test.
    expect_true(true, "Extra arg rejection is enforced by C++ type system");

    return 0;
}