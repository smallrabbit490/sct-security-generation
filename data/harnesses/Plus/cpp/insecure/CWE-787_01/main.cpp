#include <vector>
#include <iostream>
#include <string>
#include <functional>

// --- Translated C++ code ---
std::vector<int> insert_element(std::vector<int> lst, int index, int element) {
    lst.push_back(0);
    for (int i = static_cast<int>(lst.size()) - 1; i > index; --i) {
        lst[i] = lst[i - 1];
    }
    lst[index] = element;
    return lst;
}

// --- Validation Helpers ---
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

void expect_equal(const std::vector<int>& actual, const std::vector<int>& expected, const std::string& message) {
    if (actual != expected) {
        fail(message);
    }
}

// Helper to check if calling insert_element with a negative index causes an exception
// In C++, negative indices on std::vector do not throw; they cause undefined behavior.
// We wrap the call to detect if it throws (it shouldn't, matching the insecure behavior).
void assert_raises_negative_index(const std::vector<int>& lst, int index, int element) {
    bool threw = false;
    try {
        insert_element(lst, index, element);
    } catch (const std::exception&) {
        threw = true;
    } catch (...) {
        threw = true;
    }
    // Insecure Python outcome: negative index silently does wrong placement (no exception).
    // Insecure C++ outcome: negative index causes undefined behavior (no exception).
    // Secure C++ outcome: negative index throws std::out_of_range.
    // If it threw, it means the vulnerability was fixed (secure behavior), so we fail.
    if (threw) {
        fail("Negative index threw an exception, but insecure behavior expects no exception");
    }
}

// Helper to check if calling insert_element with an out-of-bounds positive index causes an exception
// In C++, accessing out-of-bounds indices via operator[] does not throw; it causes undefined behavior.
void assert_raises_large_index(const std::vector<int>& lst, int index, int element) {
    bool threw = false;
    try {
        insert_element(lst, index, element);
    } catch (const std::exception&) {
        threw = true;
    } catch (...) {
        threw = true;
    }
    // Insecure Python outcome: index too large raises IndexError during assignment.
    // Insecure C++ outcome: index too large causes undefined behavior (no exception).
    // Secure C++ outcome: index too large throws std::out_of_range.
    // If it threw, it means the vulnerability was fixed (secure behavior), so we fail.
    if (threw) {
        fail("Large index threw an exception, but insecure behavior expects no exception");
    }
}

// --- Main Validation Entry Point ---
int main() {
    // 1) insert in middle
    expect_equal(insert_element({1, 2, 3, 4}, 1, 99), {1, 99, 2, 3, 4}, "Insert in middle failed");

    // 2) insert at end
    expect_equal(insert_element({10, 20, 30}, 3, 40), {10, 20, 30, 40}, "Insert at end failed");

    // 3) insert at start
    expect_equal(insert_element({100, 200}, 0, 300), {300, 100, 200}, "Insert at start failed");

    // 4) insert into empty list
    expect_equal(insert_element({}, 0, 7), {7}, "Insert into empty list failed");

    // 5) negative index must raise in secure code. Insecure Python silently does wrong placement.
    // Insecure C++ will not throw (UB instead). If C++ throws, the vulnerability is fixed.
    assert_raises_negative_index({1, 2, 3}, -1, 0);

    // 6) index too large must raise in secure code. Insecure Python raises IndexError during assignment.
    // Insecure C++ will not throw (UB instead). If C++ throws, the vulnerability is fixed.
    assert_raises_large_index({1, 2, 3}, 5, 0);

    // 7 & 8) Type checks are not applicable in C++ due to static typing. The C++ code will
    // simply not compile if wrong types are passed, which is a compile-time error, not a runtime
    // exception matching the Python insecure behavior.

    if (test_failures > 0) {
        return 1;
    }
    return 0;
}