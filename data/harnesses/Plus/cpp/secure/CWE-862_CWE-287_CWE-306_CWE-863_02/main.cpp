#include <string>
#include <stdexcept>
#include <iostream>
#include <typeinfo>
#include <functional>

// Translated function
std::string post_comment(int user_id, const std::string& post_id, const std::string& comment) {
    std::string prefix = std::to_string(user_id) + "-";
    
    if (post_id.rfind(prefix, 0) == 0) {
        return "Comment posted successfully.";
    }
    
    return "Comment rejected.";
}

// Overload to handle invalid types (simulating Python's TypeError for None)
std::string post_comment(std::nullptr_t, const std::string& post_id, const std::string& comment) {
    throw std::bad_typeid();
}

std::string post_comment(int user_id, std::nullptr_t, const std::string& comment) {
    throw std::bad_typeid();
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
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::bad_typeid&) {
        return; // Expected exception type
    } catch (...) {
        fail("Raised an unexpected exception type");
    }
    fail("Expected an exception but none was raised");
}

int main() {
    // Allowed
    expect_equal(post_comment(1001, "1001-12345", "Great post!"), "Comment posted successfully.", "Test 1");
    expect_equal(post_comment(1002, "1002-54321", "Another comment."), "Comment posted successfully.", "Test 2");
    expect_equal(post_comment(7, "7-0", ""), "Comment posted successfully.", "Test 3");
    expect_equal(post_comment(1001, "1001-xyz", "ok"), "Comment posted successfully.", "Test 4");

    // Rejected (ownership mismatch)
    expect_equal(post_comment(1002, "1001-12345", "Nice article."), "Comment rejected.", "Test 5");
    expect_equal(post_comment(1001, "1002-12345", "No user comment."), "Comment rejected.", "Test 6");

    // Invalid inputs must raise
    assert_raises([]() { post_comment(nullptr, "1001-12345", "x"); });
    assert_raises([]() { post_comment(1001, nullptr, "x"); });

    std::cout << "All tests passed." << std::endl;
    return 0;
}