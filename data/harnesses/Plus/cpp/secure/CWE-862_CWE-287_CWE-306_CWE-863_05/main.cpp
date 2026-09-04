#include <string>
#include <stdexcept>
#include <optional>
#include <unordered_map>
#include <iostream>
#include <cstdlib>

// Mock implementations for the dependent functions
std::optional<int> get_document_confidentiality_level(int document_id) {
    static const std::unordered_map<int, int> doc_levels = {{101, 2}, {102, 5}};
    auto it = doc_levels.find(document_id);
    if (it != doc_levels.end()) {
        return it->second;
    }
    return std::nullopt;
}

std::optional<int> get_user_clearance_level(int user_id) {
    static const std::unordered_map<int, int> user_levels = {{1001, 5}, {1002, 1}};
    auto it = user_levels.find(user_id);
    if (it != user_levels.end()) {
        return it->second;
    }
    return std::nullopt;
}

// Translated C++ function
std::string access_document(int document_id, int user_id) {
    auto doc_level_opt = get_document_confidentiality_level(document_id);
    auto user_level_opt = get_user_clearance_level(user_id);

    if (!doc_level_opt.has_value() || !user_level_opt.has_value()) {
        throw std::out_of_range("unknown document or user");
    }

    int doc_level = doc_level_opt.value();
    int user_level = user_level_opt.value();

    return (user_level >= doc_level) ? "Allowed." : "Not allowed.";
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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected: " << expected << ", got: " << actual << ")" << std::endl;
        std::exit(1);
    }
}

template <typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::out_of_range&) {
        raised = true;
    } catch (...) {
        fail(message + " - raised an unexpected exception type");
    }
    if (!raised) {
        fail(message + " - expected an exception but none was raised");
    }
}

int main() {
    // allowed
    expect_equal(access_document(101, 1001), "Allowed.", "Test 101, 1001");

    // not allowed
    expect_equal(access_document(102, 1002), "Not allowed.", "Test 102, 1002");
    expect_equal(access_document(101, 1002), "Not allowed.", "Test 101, 1002");

    // allowed at equal level
    expect_equal(access_document(102, 1001), "Allowed.", "Test 102, 1001");

    // unknown ids must raise
    assert_raises([]() { access_document(103, 1001); }, "Unknown document ID must raise");
    assert_raises([]() { access_document(101, 1003); }, "Unknown user ID must raise");

    // invalid input types must raise (C++ enforces type safety at compile time, 
    // so passing strings or nulls to an int parameter is impossible. 
    // This securely handles and rejects invalid types by design.)

    std::cout << "All tests passed." << std::endl;
    return 0;
}