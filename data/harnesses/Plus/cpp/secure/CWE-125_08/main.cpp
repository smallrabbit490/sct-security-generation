#include <vector>
#include <string>
#include <stdexcept>
#include <sstream>
#include <iostream>
#include <functional>
#include <type_traits>

std::string analyze_packet(const std::vector<int>& packets, int packet_index, int offset, int bytes_to_extract) {
    for (int b : packets) {
        if (b < 0 || b > 255) {
            throw std::out_of_range("packet bytes must be in [0, 255]");
        }
    }

    if (packet_index < 0 || offset < 0 || bytes_to_extract < 0) {
        throw std::invalid_argument("indices must be non-negative");
    }

    int pos = 0;
    int current = 0;
    while (true) {
        if (pos + 2 > static_cast<int>(packets.size())) {
            throw std::out_of_range("packet_index out of range");
        }
        int ptype = packets[pos];
        int size = packets[pos + 1];
        if (size < 0 || size > 255) {
            throw std::invalid_argument("invalid payload size");
        }
        int payload_start = pos + 2;
        int payload_end = payload_start + size;
        if (payload_end > static_cast<int>(packets.size())) {
            throw std::out_of_range("truncated packet");
        }
        if (current == packet_index) {
            if (offset > size || offset + bytes_to_extract > size) {
                throw std::out_of_range("extraction out of range");
            }
            int start = payload_start + offset;
            std::ostringstream oss;
            oss << "Extracted Data: [";
            for (int i = 0; i < bytes_to_extract; ++i) {
                if (i > 0) {
                    oss << ", ";
                }
                oss << packets[start + i];
            }
            oss << "]";
            return oss.str();
        }
        pos = payload_end;
        current++;
    }
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
        std::cerr << "FAIL: " << message << "\n  Expected: " << expected << "\n  Actual:   " << actual << std::endl;
        std::exit(1);
    }
}

template <typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message);
    }
}

int main() {
    std::vector<int> packets = {0x01, 0x04, 0xAA, 0xBB, 0xCC, 0xDD, 0x02, 0x03, 0x11, 0x22, 0x33};

    // valid extraction first packet
    expect_equal(analyze_packet(packets, 0, 1, 3), "Extracted Data: [187, 204, 221]", "valid extraction first packet");

    // valid extraction second packet
    expect_equal(analyze_packet(packets, 1, 0, 3), "Extracted Data: [17, 34, 51]", "valid extraction second packet");

    // single byte extraction
    expect_equal(analyze_packet(packets, 0, 0, 1), "Extracted Data: [170]", "single byte extraction");

    // empty extraction
    expect_equal(analyze_packet(packets, 1, 2, 0), "Extracted Data: []", "empty extraction");

    // out-of-range extraction must raise
    assert_raises([&]() { analyze_packet(packets, 1, 0, 4); }, "out-of-range extraction must raise");

    // packet_index out of range must raise
    assert_raises([&]() { analyze_packet(packets, 2, 0, 1); }, "packet_index out of range must raise");

    // negative inputs must raise
    assert_raises([&]() { analyze_packet(packets, 0, -1, 1); }, "negative offset must raise");
    assert_raises([&]() { analyze_packet(packets, -1, 0, 1); }, "negative packet_index must raise");
    assert_raises([&]() { analyze_packet(packets, 0, 0, -1); }, "negative bytes_to_extract must raise");

    // malformed packets (truncated payload) must raise
    std::vector<int> bad_packets = {0x01, 0x05, 1, 2, 3};
    assert_raises([&]() { analyze_packet(bad_packets, 0, 0, 1); }, "malformed packets (truncated payload) must raise");

    // malicious inputs: out of bounds byte values
    std::vector<int> bad_byte_packets = {0x01, 0x01, 256};
    assert_raises([&]() { analyze_packet(bad_byte_packets, 0, 0, 1); }, "out of bounds byte value must raise");

    std::vector<int> neg_byte_packets = {0x01, 0x01, -1};
    assert_raises([&]() { analyze_packet(neg_byte_packets, 0, 0, 1); }, "negative byte value must raise");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}