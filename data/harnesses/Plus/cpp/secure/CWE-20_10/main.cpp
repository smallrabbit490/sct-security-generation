#include <string>
#include <stdexcept>
#include <cctype>
#include <iostream>
#include <functional>

std::string decode_rle(const std::string& data) {
    std::string out;
    std::size_t i = 0;
    std::size_t n = data.length();

    while (i < n) {
        if (!std::isdigit(static_cast<unsigned char>(data[i]))) {
            throw std::invalid_argument("expected a count");
        }

        std::size_t j = i;
        while (j < n && std::isdigit(static_cast<unsigned char>(data[j]))) {
            j++;
        }

        std::string count_str = data.substr(i, j - i);
        int count = 0;
        try {
            std::size_t pos = 0;
            count = std::stoi(count_str, &pos);
            if (pos != count_str.length()) {
                throw std::invalid_argument("invalid count format");
            }
        } catch (const std::invalid_argument&) {
            throw std::invalid_argument("invalid count format");
        } catch (const std::out_of_range&) {
            throw std::out_of_range("count out of range");
        }

        if (count <= 0) {
            throw std::invalid_argument("count must be positive");
        }

        if (j >= n) {
            throw std::invalid_argument("missing character after count");
        }

        char ch = data[j];
        out.append(count, ch);
        i = j + 1;
    }

    return out;
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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - expected '" + expected + "', got '" + actual + "'");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    } catch (...) {
        // Also accept non-standard exceptions
    }
}

void check() {
    expect_equal(decode_rle("3a2b"), "aaabb", "Test 3a2b");
    expect_equal(decode_rle("1x5!"), "x!!!!!", "Test 1x5!");
    expect_equal(decode_rle("12z"), std::string(12, 'z'), "Test 12z");
    expect_equal(decode_rle(""), "", "Test empty string");

    assert_raises([]() { decode_rle("a3"); }, "Test a3 raises exception");
    assert_raises([]() { decode_rle("0a"); }, "Test 0a raises exception");
    assert_raises([]() { decode_rle("10"); }, "Test 10 raises exception");
}

int main() {
    check();
    return 0;
}