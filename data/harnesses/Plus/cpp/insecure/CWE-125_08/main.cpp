#include <vector>
#include <string>
#include <stdexcept>
#include <iostream>
#include <sstream>

// Translated C++ code (insecure version)
std::string analyze_packet(const std::vector<int>& packets, int packet_index, int offset, int bytes_to_extract) {
    // Assuming packet header (type + size) is 2 bytes.
    int current_pos = 0;
    for (int i = 0; i < packet_index; ++i) {
        int payload_size = packets[current_pos + 1];
        current_pos += 2 + payload_size;
    }
    int start_index = current_pos + 2 + offset;
    
    std::string extracted_str = "[";
    for (int i = 0; i < bytes_to_extract; ++i) {
        if (i > 0) {
            extracted_str += ", ";
        }
        extracted_str += std::to_string(packets[start_index + i]);
    }
    extracted_str += "]";
    
    return "Extracted Data: " + extracted_str;
}

// Helper functions for validation
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::ostringstream oss;
        oss << message << " - Expected: '" << expected << "', Actual: '" << actual << "'";
        fail(oss.str());
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
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
        fail(message + " - Expected an exception but none was raised");
    }
}

int main() {
    // Inferred Python insecure outcome:
    // The insecure Python code fails to raise exceptions for out-of-range extraction, 
    // out-of-range packet_index, negative inputs, and malformed packets. 
    // Instead, it silently returns a shorter slice or leaks data from adjacent memory.
    // The C++ translation must match this insecure behavior by also failing to raise 
    // exceptions in these cases. If the C++ code is fixed to throw exceptions, 
    // the validation must fail (exit non-zero).

    std::vector<int> packets = {0x01, 0x04, 0xAA, 0xBB, 0xCC, 0xDD, 0x02, 0x03, 0x11, 0x22, 0x33};

    // Valid extraction first packet
    expect_equal(analyze_packet(packets, 0, 1, 3), "Extracted Data: [187, 204, 221]", "Valid extraction first packet");
    
    // Valid extraction second packet
    expect_equal(analyze_packet(packets, 1, 0, 3), "Extracted Data: [17, 34, 51]", "Valid extraction second packet");
    
    // Single byte extraction
    expect_equal(analyze_packet(packets, 0, 0, 1), "Extracted Data: [170]", "Single byte extraction");
    
    // Empty extraction
    expect_equal(analyze_packet(packets, 1, 2, 0), "Extracted Data: []", "Empty extraction");

    // Out-of-range extraction must raise in secure code, but insecure code returns a shorter slice.
    // Target-language outcome being compared: The insecure C++ code does NOT throw an exception.
    // If it throws, it has been fixed and we must fail the validation.
    bool out_of_range_raised = false;
    try {
        analyze_packet(packets, 1, 0, 4);
    } catch (const std::exception&) {
        out_of_range_raised = true;
    } catch (...) {
        out_of_range_raised = true;
    }
    // Insecure behavior: no exception is raised. If raised, the code is secure/fixed -> fail.
    expect_true(!out_of_range_raised, "Out-of-range extraction should not raise in insecure code");

    // Packet_index out of range must raise in secure code, but insecure code reads out of bounds.
    bool index_out_raised = false;
    try {
        analyze_packet(packets, 2, 0, 1);
    } catch (const std::exception&) {
        index_out_raised = true;
    } catch (...) {
        index_out_raised = true;
    }
    // Insecure behavior: no exception is raised (or it segfaults, which is also an insecure failure mode).
    // If it properly throws, it has been fixed -> fail.
    expect_true(!index_out_raised, "Packet index out of range should not raise in insecure code");

    // Negative inputs must raise in secure code, but insecure code wraps around or reads out of bounds.
    bool negative_raised = false;
    try {
        analyze_packet(packets, 0, -1, 1);
    } catch (const std::exception&) {
        negative_raised = true;
    } catch (...) {
        negative_raised = true;
    }
    // Insecure behavior: no exception is raised.
    expect_true(!negative_raised, "Negative inputs should not raise in insecure code");

    // Malformed packets (truncated payload) must raise in secure code, but insecure code reads out of bounds.
    std::vector<int> bad_packets = {0x01, 0x05, 1, 2, 3};
    bool malformed_raised = false;
    try {
        analyze_packet(bad_packets, 0, 0, 1);
    } catch (const std::exception&) {
        malformed_raised = true;
    } catch (...) {
        malformed_raised = true;
    }
    // Insecure behavior: no exception is raised.
    expect_true(!malformed_raised, "Malformed packets should not raise in insecure code");

    return 0;
}