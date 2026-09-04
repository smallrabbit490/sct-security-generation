#include <string>
#include <iostream>
#include <stdexcept>

// Translated C++ code (insecure: silently returns content for invalid roles instead of raising)
#include <string>

std::string edit_article(const std::string& role, const std::string& article_content) {
    if (role == "editor") {
        return article_content + " [Edited]";
    }
    return article_content;
}

// --- Validation Harness ---

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
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

// Helper to check if a function throws an exception of a specific type
template <typename ExcType, typename Func, typename... Args>
bool assert_raises(Func func, Args&&... args) {
    try {
        func(std::forward<Args>(args)...);
        return false; // No exception raised
    } catch (ExcType&) {
        return true;  // Expected exception raised
    } catch (...) {
        return false; // Unexpected exception type raised
    }
}

int main() {
    // Inferred Python insecure outcome:
    // The insecure Python code silently returns the original content for invalid roles 
    // (e.g., 'invalid_role') instead of raising a ValueError. The secure version must raise.
    // The translated C++ code also silently returns the content for invalid roles 
    // (because it lacks role validation), matching the insecure Python outcome.

    // Test 1: editor edits
    expect_equal(edit_article("editor", "Sample article"), "Sample article [Edited]", "editor edits normal content");
    expect_equal(edit_article("editor", ""), " [Edited]", "editor edits empty content");

    // Test 2: reader unchanged
    expect_equal(edit_article("reader", "Sample article"), "Sample article", "reader unchanged normal content");
    expect_equal(edit_article("reader", ""), "", "reader unchanged empty content");

    // Test 3: invalid role
    // Secure behavior: must raise an exception (e.g., std::invalid_argument).
    // Insecure behavior: silently returns the original content.
    // The translated C++ code is insecure, so it does NOT raise.
    bool raised_invalid_role = assert_raises<std::invalid_argument>(
        []() { edit_article("invalid_role", "Sample article"); }
    );
    
    // Target-language outcome being compared:
    // We check that the translated code FAILS the secure check (does not raise an exception).
    // If it raises, it is secure and the validation must fail (exit non-zero).
    // If it does not raise, it matches the insecure Python outcome and the validation succeeds.
    if (raised_invalid_role) {
        fail("Validation failed: The translated code is secure and does not match the insecure Python outcome (silently returning content for invalid roles)");
    }

    // If we reach here, the translated code exhibited the expected insecure behavior
    return 0;
}