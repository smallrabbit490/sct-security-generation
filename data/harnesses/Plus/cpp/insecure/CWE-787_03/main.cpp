#include <vector>
#include <stdexcept>
#include <iostream>
#include <string>

// Translated C++ code (insecure)
std::vector<int> swap_segments(std::vector<int> buf, int a_start, int b_start, int seg_len) {
    // Insecure: no bounds/overlap checks; negative indexing can silently corrupt,
    // and out-of-range may throw mid-swap leaving partial modifications.
    for (int i = 0; i < seg_len; ++i) {
        int tmp = buf.at(a_start + i);
        buf.at(a_start + i) = buf.at(b_start + i);
        buf.at(b_start + i) = tmp;
    }
    return buf;
}

// Helper functions for validation
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
        fail(message);
    }
}

// Helper to check that a function throws std::out_of_range
template<typename Func>
void assert_throws_out_of_range(Func f, const std::string& message) {
    bool threw = false;
    try {
        f();
    } catch (const std::out_of_range&) {
        threw = true;
    } catch (...) {
        // Threw something else
    }
    if (!threw) {
        fail(message);
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python insecure code lacks bounds/overlap checks. For out-of-bounds or negative indices,
     * Python will raise an IndexError mid-swap, leaving the buffer partially modified.
     * For overlapping segments, it silently corrupts the data instead of raising ValueError.
     * For invalid seg_len (0), it silently does nothing instead of raising ValueError.
     *
     * Target-language (C++) insecure outcome:
     * The C++ insecure translation uses std::vector::at(), which throws std::out_of_range for
     * out-of-bounds or negative indices (since size_t wraps negative to large positive).
     * This matches the Python insecure behavior of raising an exception mid-swap for bad indices.
     * For overlapping segments or seg_len=0, it also silently corrupts or does nothing, matching Python.
     *
     * Validation rule:
     * We validate that the C++ code fails in the same security-relevant way as the Python code.
     * If the C++ code were "fixed" to check bounds/overlap and throw proper exceptions for
     * overlaps/invalid lengths, or if it used operator[] and crashed via assertion instead of
     * throwing std::out_of_range, the validation must fail (exit non-zero).
     */

    // 1) Normal swap
    std::vector<int> r1 = swap_segments({1, 2, 3, 4, 5, 6}, 0, 3, 2);
    expect_equal(r1, {4, 5, 3, 1, 2, 6}, "Test 1 failed: normal swap");

    // 2) Swap single element segments
    std::vector<int> r3 = swap_segments({9, 8, 7}, 0, 2, 1);
    expect_equal(r3, {7, 8, 9}, "Test 3 failed: single element swap");

    // 3) Out-of-bounds segment must throw (insecure throws std::out_of_range mid-swap, matching Python IndexError)
    assert_throws_out_of_range([]() {
        swap_segments({1, 2, 3}, 2, 0, 2);
    }, "Test 5 failed: out-of-bounds did not throw std::out_of_range");

    // 4) Negative start must throw (insecure throws std::out_of_range due to size_t wrap, matching Python IndexError)
    assert_throws_out_of_range([]() {
        swap_segments({1, 2, 3}, -1, 1, 1);
    }, "Test 6 failed: negative start did not throw std::out_of_range");

    // 5) Overlapping segments must NOT throw (insecure silently corrupts, matching Python)
    // If the code were fixed to throw ValueError/logic_error, this would fail the insecure validation.
    try {
        std::vector<int> r7 = swap_segments({1, 2, 3, 4}, 1, 2, 2);
        // Insecure code silently returns corrupted data instead of throwing
        expect_true(true, "Test 7: overlapping segments did not throw (insecure behavior)");
    } catch (const std::logic_error&) {
        fail("Test 7 failed: overlapping segments threw logic_error (secure behavior), expected no throw (insecure)");
    } catch (...) {
        fail("Test 7 failed: overlapping segments threw unexpected exception");
    }

    // 6) seg_len invalid (0) must NOT throw (insecure silently does nothing, matching Python)
    try {
        std::vector<int> r8 = swap_segments({1, 2}, 0, 1, 0);
        expect_true(true, "Test 8: seg_len 0 did not throw (insecure behavior)");
    } catch (const std::logic_error&) {
        fail("Test 8 failed: seg_len 0 threw logic_error (secure behavior), expected no throw (insecure)");
    } catch (...) {
        fail("Test 8 failed: seg_len 0 threw unexpected exception");
    }

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}