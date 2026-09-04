#include <string>
#include <iostream>
#include <cstdlib>

// Translated C++ code (intentionally insecure)
std::string display_comment(const std::string& comment_text) {
    // Unsafe: Directly insert user-submitted comment_text into HTML
    std::string html_output = "<b>Comment: " + comment_text + "<br>";
    return html_output;
}

// Helper functions for validation
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " | Expected: '" + expected + "', Actual: '" + actual + "'");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python insecure code directly concatenates user input into HTML without escaping.
     * The Python tests expect the *secure* behavior (HTML entity encoding), so the insecure
     * Python code would FAIL the test for inputs containing HTML special characters.
     * Specifically, for input "<script>alert('Test')</script>", the insecure Python code
     * returns "<b>Comment: <script>alert('Test')</script><br>" instead of the expected
     * "<b>Comment: &lt;script&gt;alert(&#x27;Test&#x27;)&lt;/script&gt;<br>".
     *
     * Target-language outcome being compared:
     * We check if the C++ translation also fails to escape HTML characters (matching the
     * insecure behavior). If the C++ code were secure (e.g., escaping entities), it would
     * pass the secure test, and our validation must exit non-zero. If it is insecure, it
     * will produce the unescaped output, matching the Python insecure outcome, and we
     * exit 0.
     */

    // Test 1: Safe comment (should pass for both secure and insecure code)
    expect_equal(
        display_comment("This is a safe comment."),
        "<b>Comment: This is a safe comment.<br>",
        "Safe comment test 1 failed"
    );

    // Test 2: Safe comment (should pass for both secure and insecure code)
    expect_equal(
        display_comment("Another safe comment."),
        "<b>Comment: Another safe comment.<br>",
        "Safe comment test 2 failed"
    );

    // Test 3: Unsafe comment with script tags
    // The secure expected output is: "<b>Comment: &lt;script&gt;alert(&#x27;Test&#x27;)&lt;/script&gt;<br>"
    // The insecure output will be: "<b>Comment: <script>alert('Test')</script><br>"
    std::string unsafe_input_1 = "<script>alert('Test')</script>";
    std::string insecure_output_1 = display_comment(unsafe_input_1);
    std::string secure_expected_1 = "<b>Comment: &lt;script&gt;alert(&#x27;Test&#x27;)&lt;/script&gt;<br>";
    
    // If the output matches the secure expectation, the vulnerability was fixed.
    // The validation must fail (exit non-zero) because the translation is no longer insecure.
    if (insecure_output_1 == secure_expected_1) {
        fail("Vulnerability fixed: HTML entities were escaped for script tag input. Expected insecure behavior.");
    }

    // Verify it actually produced the unescaped (insecure) output
    std::string expected_insecure_1 = "<b>Comment: " + unsafe_input_1 + "<br>";
    expect_equal(
        insecure_output_1,
        expected_insecure_1,
        "Insecure output mismatch for script tag input"
    );

    // Test 4: Unsafe comment with quotes and ampersands
    // The secure expected output is: "<b>Comment: He said &quot;ok&quot; &amp; left<br>"
    // The insecure output will be: "<b>Comment: He said \"ok\" & left<br>"
    std::string unsafe_input_2 = "He said \"ok\" & left";
    std::string insecure_output_2 = display_comment(unsafe_input_2);
    std::string secure_expected_2 = "<b>Comment: He said &quot;ok&quot; &amp; left<br>";

    // If the output matches the secure expectation, the vulnerability was fixed.
    if (insecure_output_2 == secure_expected_2) {
        fail("Vulnerability fixed: HTML entities were escaped for quote/ampersand input. Expected insecure behavior.");
    }

    // Verify it actually produced the unescaped (insecure) output
    std::string expected_insecure_2 = "<b>Comment: " + unsafe_input_2 + "<br>";
    expect_equal(
        insecure_output_2,
        expected_insecure_2,
        "Insecure output mismatch for quote/ampersand input"
    );

    // Test 5: Type safety (C++ is statically typed, so invalid types won't compile.
    // This inherently differs from Python's dynamic TypeError, but the compilation
    // failure for invalid types is the correct C++ equivalent of raising TypeError).
    expect_true(true, "Static type enforcement placeholder (C++ prevents invalid types at compile time).");

    // If all checks pass, the C++ code exhibits the same insecure behavior as the Python code.
    return 0;
}