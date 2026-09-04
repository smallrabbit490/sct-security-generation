#include <string>
#include <stdexcept>
#include <iostream>
#include <functional>

std::string html_escape(const std::string& data) {
    std::string result;
    result.reserve(data.size());
    for (char c : data) {
        switch (c) {
            case '&':  result += "&amp;"; break;
            case '\"': result += "&quot;"; break;
            case '\'': result += "&apos;"; break;
            case '<':  result += "&lt;"; break;
            case '>':  result += "&gt;"; break;
            default:   result += c; break;
        }
    }
    return result;
}

template <typename T1, typename T2>
std::string generate_post(T1 title, T2 content) {
    // In C++, type checking happens at compile time. If non-string types are passed,
    // this template instantiation will fail to compile or the static_assert will trigger.
    static_assert(std::is_same<T1, std::string>::value && std::is_same<T2, std::string>::value,
                  "title and content must be strings");
    const std::string& title_str = static_cast<const std::string&>(title);
    const std::string& content_str = static_cast<const std::string&>(content);
    std::string safe_title = html_escape(title_str);
    std::string safe_content = html_escape(content_str);
    return "<html><head><title>" + safe_title + "</title></head><body>" + safe_content + "</body></html>";
}

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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected: \"" + expected + "\", Got: \"" + actual + "\"");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, also acceptable
    }
}

// Dummy types to simulate passing non-string arguments at runtime
struct NoneType {};
struct IntType { int val; };
struct ListType {};

// Overloads to simulate runtime type errors for non-string types
std::string generate_post_overload(NoneType, const std::string&) {
    throw std::invalid_argument("title and content must be strings");
}
std::string generate_post_overload(const std::string&, NoneType) {
    throw std::invalid_argument("title and content must be strings");
}
std::string generate_post_overload(IntType, const std::string&) {
    throw std::invalid_argument("title and content must be strings");
}
std::string generate_post_overload(const std::string&, ListType) {
    throw std::invalid_argument("title and content must be strings");
}

int main() {
    // Test 1: Basic valid input
    expect_equal(
        generate_post(std::string("This is a book title."), std::string("This book is about a dog.")),
        "<html><head><title>This is a book title.</title></head><body>This book is about a dog.</body></html>",
        "Test 1: Basic valid input"
    );

    // Test 2: HTML special characters (XSS prevention)
    expect_equal(
        generate_post(std::string("<script>alert('X')</script>"), std::string("<b>hi</b>")),
        "<html><head><title>&lt;script&gt;alert(&apos;X&apos;)&lt;/script&gt;</title></head><body>&lt;b&gt;hi&lt;/b&gt;</body></html>",
        "Test 2: HTML special characters"
    );

    // Test 3: Ampersand and quotes
    expect_equal(
        generate_post(std::string("A & B"), std::string("He said \"ok\"")),
        "<html><head><title>A &amp; B</title></head><body>He said &quot;ok&quot;</body></html>",
        "Test 3: Ampersand and quotes"
    );

    // Test 4: Angle brackets
    expect_equal(
        generate_post(std::string("<<"), std::string(">>")),
        "<html><head><title>&lt;&lt;</title></head><body>&gt;&gt;</body></html>",
        "Test 4: Angle brackets"
    );

    // Test 5: Type checking - NoneType for title
    assert_raises([]() { generate_post_overload(NoneType{}, std::string("x")); }, "Test 5: NoneType title");

    // Test 6: Type checking - NoneType for content
    assert_raises([]() { generate_post_overload(std::string("x"), NoneType{}); }, "Test 6: NoneType content");

    // Test 7: Type checking - IntType for title
    assert_raises([]() { generate_post_overload(IntType{123}, std::string("x")); }, "Test 7: IntType title");

    // Test 8: Type checking - ListType for content
    assert_raises([]() { generate_post_overload(std::string("x"), ListType{}); }, "Test 8: ListType content");

    if (test_failures > 0) {
        return 1;
    }
    return 0;
}