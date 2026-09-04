#include <string>
#include <stdexcept>
#include <iostream>
#include <functional>

// Translated display_comment function
std::string display_comment(const std::string& comment_text) {
    std::string encoded_comment_text;
    encoded_comment_text.reserve(comment_text.size());
    for (char c : comment_text) {
        switch (c) {
            case '&':  encoded_comment_text += "&amp;"; break;
            case '<':  encoded_comment_text += "&lt;"; break;
            case '>':  encoded_comment_text += "&gt;"; break;
            case '"':  encoded_comment_text += "&quot;"; break;
            case '\'': encoded_comment_text += "&#x27;"; break;
            default:   encoded_comment_text += c; break;
        }
    }
    return "<b>Comment: " + encoded_comment_text + "<br>";
}

// Overload to handle non-string arguments and raise an exception
std::string display_comment(int) {
    throw std::invalid_argument("comment_text must be a string");
}

// Overload to handle null pointer arguments and raise an exception
std::string display_comment(std::nullptr_t) {
    throw std::invalid_argument("comment_text must be a string");
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
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: " << expected << std::endl;
        std::cerr << "  Actual:   " << actual << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::invalid_argument&) {
        return; // Successfully caught the expected exception type
    } catch (const std::exception& e) {
        fail("Raised an unexpected exception type: " + std::string(e.what()));
    }
    fail("Expected an exception but none was raised");
}

int main() {
    // Test safe comments
    expect_equal(
        display_comment("This is a safe comment."),
        "<b>Comment: This is a safe comment.<br>",
        "Safe comment 1 failed"
    );

    expect_equal(
        display_comment("Another safe comment."),
        "<b>Comment: Another safe comment.<br>",
        "Safe comment 2 failed"
    );

    // Test HTML/XSS escaping
    expect_equal(
        display_comment("<script>alert('Test')</script>"),
        "<b>Comment: &lt;script&gt;alert(&#x27;Test&#x27;)&lt;/script&gt;<br>",
        "Script tag escaping failed"
    );

    expect_equal(
        display_comment("He said \"ok\" & left"),
        "<b>Comment: He said &quot;ok&quot; &amp; left<br>",
        "Quotes and ampersand escaping failed"
    );

    // Test type checking (invalid arguments)
    assert_raises([]() { display_comment(nullptr); });
    assert_raises([]() { display_comment(123); });

    // If all tests pass
    return 0;
}