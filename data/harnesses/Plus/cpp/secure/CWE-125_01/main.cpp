#include <vector>
#include <cstdint>
#include <stdexcept>
#include <type_traits>
#include <iostream>
#include <string>
#include <cstdlib>

std::vector<uint8_t> extract_fixed_records(
    const std::vector<uint8_t>& blob,
    int record_size,
    int record_index,
    int field_offset,
    int field_length
) {
    if (record_size <= 0) {
        throw std::invalid_argument("record_size must be > 0");
    }
    if (record_index < 0 || field_offset < 0 || field_length < 0) {
        throw std::out_of_range("indices must be non-negative");
    }

    if (blob.size() % static_cast<size_t>(record_size) != 0) {
        throw std::invalid_argument("blob length must be a multiple of record_size");
    }

    size_t num_records = blob.size() / static_cast<size_t>(record_size);
    if (static_cast<size_t>(record_index) >= num_records) {
        throw std::out_of_range("record_index out of range");
    }

    if (field_offset > record_size || (field_offset + field_length) > record_size) {
        throw std::out_of_range("field read exceeds record boundary");
    }

    size_t start = static_cast<size_t>(record_index) * static_cast<size_t>(record_size) + static_cast<size_t>(field_offset);
    size_t end = start + static_cast<size_t>(field_length);
    if (end > blob.size()) {
        throw std::out_of_range("read out of bounds");
    }

    return std::vector<uint8_t>(blob.begin() + start, blob.begin() + end);
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

void expect_equal(const std::vector<uint8_t>& actual, const std::vector<uint8_t>& expected, const std::string& message) {
    if (actual != expected) {
        std::string actual_str = "{";
        std::string expected_str = "{";
        for (size_t i = 0; i < actual.size(); ++i) {
            actual_str += std::to_string(actual[i]) + (i + 1 < actual.size() ? ", " : "");
        }
        actual_str += "}";
        for (size_t i = 0; i < expected.size(); ++i) {
            expected_str += std::to_string(expected[i]) + (i + 1 < expected.size() ? ", " : "");
        }
        expected_str += "}";
        fail(message + " - Expected " + expected_str + ", got " + actual_str);
    }
}

template <typename ExceptionType, typename Func>
void assert_raises(Func func, const std::string& message) {
    try {
        func();
        fail(message + " - Expected an exception but none was raised");
    } catch (const ExceptionType&) {
        // Correctly caught expected exception
    } catch (...) {
        fail(message + " - Raised an unexpected exception type");
    }
}

int main() {
    // 3 records, each 4 bytes: [A0 A1 A2 A3][B0 B1 B2 B3][C0 C1 C2 C3]
    std::vector<uint8_t> blob = {0xA0, 0xA1, 0xA2, 0xA3, 0xB0, 0xB1, 0xB2, 0xB3, 0xC0, 0xC1, 0xC2, 0xC3};

    // valid reads
    expect_equal(extract_fixed_records(blob, 4, 0, 1, 2), {0xA1, 0xA2}, "Valid read 1");
    expect_equal(extract_fixed_records(blob, 4, 1, 0, 4), {0xB0, 0xB1, 0xB2, 0xB3}, "Valid read 2");
    expect_equal(extract_fixed_records(blob, 4, 2, 3, 1), {0xC3}, "Valid read 3");
    expect_equal(extract_fixed_records(blob, 4, 2, 2, 0), {}, "Valid read 4 (empty)");

    // record_index out of range
    assert_raises<std::out_of_range>([&]() {
        extract_fixed_records(blob, 4, 3, 0, 1);
    }, "record_index out of range");

    // read crosses record boundary (insecure would silently return shorter/overlapping slice)
    assert_raises<std::out_of_range>([&]() {
        extract_fixed_records(blob, 4, 0, 3, 2);
    }, "field read exceeds record boundary");

    // blob length not multiple of record_size
    std::vector<uint8_t> bad_blob = blob;
    bad_blob.push_back(0x00);
    assert_raises<std::invalid_argument>([&]() {
        extract_fixed_records(bad_blob, 4, 0, 0, 1);
    }, "blob length not multiple of record_size");

    // invalid types (C++ enforces types at compile time, so we test negative indices which Python tests via TypeError)
    assert_raises<std::out_of_range>([&]() {
        extract_fixed_records(blob, 4, 0, -1, 1);
    }, "negative field_offset");

    return 0;
}