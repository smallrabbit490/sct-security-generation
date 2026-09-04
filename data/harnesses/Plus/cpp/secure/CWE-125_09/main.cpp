#include <vector>
#include <string>
#include <stdexcept>
#include <cstdint>
#include <iostream>
#include <functional>
#include <typeinfo>

std::string extract_c_string(const std::vector<uint8_t>& buf, int start) {
    if (start < 0 || start >= static_cast<int>(buf.size())) {
        throw std::out_of_range("start out of range");
    }

    std::string out;
    int i = start;
    while (i < static_cast<int>(buf.size())) {
        uint8_t b = buf[i];
        if (b == 0) {
            return out;
        }
        out += static_cast<char>(b);
        i++;
    }

    throw std::runtime_error("missing null terminator");
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
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

template <typename ExcType>
void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const ExcType&) {
        // Correctly raised expected exception
    } catch (...) {
        fail(message + " - Raised an unexpected exception type");
    }
}

int main() {
    std::vector<uint8_t> buf = {'H', 'E', 'L', 'L', 'O', 0, 'W', 'O', 'R', 'L', 'D', 0};

    expect_equal(extract_c_string(buf, 0), "HELLO", "Extract HELLO from start 0");
    expect_equal(extract_c_string(buf, 6), "WORLD", "Extract WORLD from start 6");
    
    std::vector<uint8_t> buf_a = {'A', 0};
    expect_equal(extract_c_string(buf_a, 0), "A", "Extract single char A");
    
    std::vector<uint8_t> buf_null = {0};
    expect_equal(extract_c_string(buf_null, 0), "", "Extract empty string from single null");

    // start out of range
    assert_raises<std::out_of_range>([&buf]() { extract_c_string(buf, -1); }, "Negative start index");
    assert_raises<std::out_of_range>([&buf]() { extract_c_string(buf, static_cast<int>(buf.size())); }, "Start index equals buffer size");

    // missing terminator
    std::vector<uint8_t> buf_no_term = {'N', 'O', '_', 'T', 'E', 'R', 'M'};
    assert_raises<std::runtime_error>([&buf_no_term]() { extract_c_string(buf_no_term, 0); }, "Missing null terminator");

    // wrong types (C++ enforces types at compile-time, so we verify the function signature rejects bad types)
    // extract_c_string("not-bytes", 0); // Compile-time error: const char* is not std::vector<uint8_t>
    // extract_c_string(buf, "0");       // Compile-time error: const char* is not int
    
    expect_true(std::is_same<decltype(extract_c_string), std::string(const std::vector<uint8_t>&, int)>::value,
                "Function signature enforces correct types");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}