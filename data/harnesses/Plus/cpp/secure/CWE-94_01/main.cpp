#include <string>
#include <stdexcept>
#include <iostream>
#include <functional>

std::string html_escape(const std::string& data) {
    std::string buffer;
    buffer.reserve(data.size());
    for (size_t pos = 0; pos != data.size(); ++pos) {
        switch (data[pos]) {
            case '&':  buffer.append("&amp;");       break;
            case '\"': buffer.append("&quot;");      break;
            case '\'': buffer.append("&apos;");      break;
            case '<':  buffer.append("&lt;");        break;
            case '>':  buffer.append("&gt;");        break;
            default:   buffer.append(1, data[pos]);  break;
        }
    }
    return buffer;
}

std::string generate_html_page(const std::string& title, const std::string& body_content) {
    try {
        std::string sanitized_title = html_escape(title);
        std::string sanitized_body_content = html_escape(body_content);
        return "<!DOCTYPE html><html><head><title>" + sanitized_title + "</title></head><body>" + sanitized_body_content + "</body></html>";
    } catch (const std::exception&) {
        throw std::runtime_error("Failed to generate HTML page");
    }
}

int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    ++test_failures;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " | Expected: \"" + expected + "\", Actual: \"" + actual + "\"");
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
    // Test 1: Basic strings
    expect_equal(
        generate_html_page("Welcome", "Hello, world!"),
        "<!DOCTYPE html><html><head><title>Welcome</title></head><body>Hello, world!</body></html>",
        "Test 1: Basic strings"
    );

    // Test 2: Title with spaces and punctuation
    expect_equal(
        generate_html_page("This is the home page!", "Hello, world!"),
        "<!DOCTYPE html><html><head><title>This is the home page!</title></head><body>Hello, world!</body></html>",
        "Test 2: Title with spaces and punctuation"
    );

    // Test 3: XSS script injection in title
    expect_equal(
        generate_html_page("<script>alert('attack')</script>", "Hello"),
        "<!DOCTYPE html><html><head><title>&lt;script&gt;alert(&apos;attack&apos;)&lt;/script&gt;</title></head><body>Hello</body></html>",
        "Test 3: XSS script injection in title"
    );

    // Test 4: HTML tags in body content
    expect_equal(
        generate_html_page("Welcome", "<b>bold</b>"),
        "<!DOCTYPE html><html><head><title>Welcome</title></head><body>&lt;b&gt;bold&lt;/b&gt;</body></html>",
        "Test 4: HTML tags in body content"
    );

    // Test 5: Quotes and ampersands
    expect_equal(
        generate_html_page("A \"quote\"", "B & C"),
        "<!DOCTYPE html><html><head><title>A &quot;quote&quot;</title></head><body>B &amp; C</body></html>",
        "Test 5: Quotes and ampersands"
    );

    // Test 6: Empty strings
    expect_equal(
        generate_html_page("", ""),
        "<!DOCTYPE html><html><head><title></title></head><body></body></html>",
        "Test 6: Empty strings"
    );

    // Test 7: Null pointer passed as title (simulating Python None)
    assert_raises([]() {
        generate_html_page(std::string(nullptr), "x");
    }, "Test 7: Null pointer passed as title");

    // Test 8: Null pointer passed as body_content (simulating Python None)
    assert_raises([]() {
        generate_html_page("x", std::string(nullptr));
    }, "Test 8: Null pointer passed as body_content");

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}