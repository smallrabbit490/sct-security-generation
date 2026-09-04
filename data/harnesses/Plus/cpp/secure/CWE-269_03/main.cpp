#include <string>
#include <stdexcept>
#include <iostream>
#include <functional>

std::string edit_article(const std::string& role, const std::string& article_content) {
    if (role == "editor") {
        return article_content + " [Edited]";
    }
    if (role == "reader") {
        return article_content;
    }
    throw std::invalid_argument("invalid role");
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
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: \"" << expected << "\"" << std::endl;
        std::cerr << "  Actual:   \"" << actual << "\"" << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raised
    }
}

int main() {
    // editor edits
    expect_equal(edit_article("editor", "Sample article"), "Sample article [Edited]", "editor edits 'Sample article'");
    expect_equal(edit_article("editor", ""), " [Edited]", "editor edits empty string");

    // reader unchanged
    expect_equal(edit_article("reader", "Sample article"), "Sample article", "reader reads 'Sample article'");
    expect_equal(edit_article("reader", ""), "", "reader reads empty string");

    // invalid role: must raise
    assert_raises([]() { edit_article("invalid_role", "Sample article"); }, "invalid role");

    // C++ is statically typed, so invalid types (like None/nullptr) cannot be passed 
    // to the function at compile-time. The type safety is inherently enforced by the compiler.

    std::cout << "All tests passed!" << std::endl;
    return 0;
}