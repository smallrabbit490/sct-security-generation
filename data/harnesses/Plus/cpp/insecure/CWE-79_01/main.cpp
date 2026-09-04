#include <string>
#include <iostream>
#include <cstdlib>

// Inferred Python insecure outcome:
// The Python code directly interpolates `title` and `content` into the HTML string
// without escaping. When the secure tests pass HTML special characters (like `<`, `>`,
// `&`, `"`, `'`), the insecure Python code will return them unescaped, failing the
// secure assertions that expect HTML entity equivalents (e.g., `&lt;`, `&gt;`).
// The Python code also fails to raise TypeError for invalid inputs (like None or int),
// instead raising AttributeError or other errors, failing the secure type checks.

// Target-language insecure outcome being compared:
// The C++ translation also directly concatenates `title` and `content` into the HTML
// string without escaping. It similarly fails to validate types (as C++ types are
// strictly enforced at compile time and won't accept None/int dynamically).
// For the validation to succeed (exit 0), the C++ code must produce the same
// insecure/unescaped output as the Python code for the given inputs, proving the
// vulnerability was translated. If the C++ code were fixed to escape HTML entities,
// it would pass the secure assertions, and this validation must exit non-zero.

std::string generate_post(const std::string& title, const std::string& content) {
    return "<html><head><title>" + title + "</title></head><body>" + content + "</body></html>";
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected: \"" + expected + "\", Got: \"" + actual + "\"");
    }
}

int main() {
    // Test 1: Normal input (both secure and insecure code pass this)
    expect_equal(
        generate_post("This is a book title.", "This book is about a dog."),
        "<html><head><title>This is a book title.</title></head><body>This book is about a dog.</body></html>",
        "Test 1: Normal input"
    );

    // Test 2: HTML injection characters (secure code escapes them, insecure code does not)
    // The insecure C++ translation must return the unescaped string to match the Python vulnerability.
    expect_equal(
        generate_post("<script>alert('X')</script>", "<b>hi</b>"),
        "<html><head><title><script>alert('X')</script></title></head><body><b>hi</b></body></html>",
        "Test 2: Unescaped HTML injection"
    );

    // Test 3: Ampersand and quotes (secure code escapes them, insecure code does not)
    expect_equal(
        generate_post("A & B", "He said \"ok\""),
        "<html><head><title>A & B</title></head><body>He said \"ok\"</body></html>",
        "Test 3: Unescaped ampersand and quotes"
    );

    // Test 4: Angle brackets (secure code escapes them, insecure code does not)
    expect_equal(
        generate_post("<<", ">>"),
        "<html><head><title><<</title></head><body>>></body></html>",
        "Test 4: Unescaped angle brackets"
    );

    // Note on TypeError checks:
    // The Python tests check that TypeError is raised for None or int arguments.
    // In C++, the strict typing of `const std::string&` prevents such calls from
    // compiling at all. Since the C++ code inherently rejects invalid types by
    // design of the language, it does not "accept" them insecurely like Python.
    // The primary vulnerability here is the XSS/HTML injection, which the above
    // string comparison tests validate correctly against the insecure behavior.

    std::cout << "All insecure behavior checks passed." << std::endl;
    return 0;
}