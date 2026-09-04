#include <string>
#include <map>
#include <stdexcept>
#include <iostream>

// Translated C++ code
std::map<std::string, std::string> create_article(const std::string& title, const std::string& content) {
    std::map<std::string, std::string> article_data;
    article_data["title"] = title;
    article_data["content"] = content;
    return article_data;
}

// Helper functions for validation
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

int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python code does not perform HTML escaping on the title and content inputs.
     * When the secure test expects HTML entities (e.g., '<' -> '&lt;', '&' -> '&amp;'),
     * the insecure Python code returns the raw, unescaped strings instead.
     * The validation must succeed (exit 0) when the C++ translation also fails to escape
     * (i.e., returns raw strings matching the insecure behavior), and fail (exit non-zero)
     * if the C++ translation securely escapes the characters.
     *
     * Target-language outcome being compared:
     * We check that create_article returns the raw, unescaped characters for inputs
     * containing HTML markup. If it returns escaped strings, the vulnerability is fixed,
     * and we must exit non-zero.
     */

    // Test 1: Normal strings (no special characters, secure and insecure behave the same)
    auto result1 = create_article("Golden Retriever", "Golden Retrievers are cute.");
    expect_equal(result1["title"], "Golden Retriever", "Test 1 title");
    expect_equal(result1["content"], "Golden Retrievers are cute.", "Test 1 content");

    // Test 2: HTML tags in title and content
    // Insecure Python outcome: returns raw unescaped strings
    auto result2 = create_article("An <strong>Important</strong> Announcement", "Please be aware of <script>alert('x')</script>.");
    // If the C++ code securely escapes, it would return "An &lt;strong&gt;Important&lt;/strong&gt; Announcement"
    // We expect the INSECURE behavior: raw unescaped strings
    expect_equal(result2["title"], "An <strong>Important</strong> Announcement", "Test 2 title - must be unescaped (insecure)");
    expect_equal(result2["content"], "Please be aware of <script>alert('x')</script>.", "Test 2 content - must be unescaped (insecure)");

    // Test 3: HTML entities & and >
    // Insecure Python outcome: returns raw unescaped strings
    auto result3 = create_article("A & B", "C > D");
    expect_equal(result3["title"], "A & B", "Test 3 title - must be unescaped (insecure)");
    expect_equal(result3["content"], "C > D", "Test 3 content - must be unescaped (insecure)");

    // Test 4: Double quotes
    // Insecure Python outcome: returns raw unescaped strings
    auto result4 = create_article("He said \"ok\"", "Done");
    expect_equal(result4["title"], "He said \"ok\"", "Test 4 title - must be unescaped (insecure)");
    expect_equal(result4["content"], "Done", "Test 4 content");

    // Note on type checking:
    // The Python tests check that passing None or non-string types raises a TypeError.
    // The C++ version uses std::string, which inherently enforces type safety at compile time
    // (preventing None/int/dict from being passed). This is a secure behavior (preventing
    // type confusion vulnerabilities), but since the Python insecure code fails the test
    // by raising a TypeError at runtime, and the C++ code prevents it at compile time,
    // we don't need to explicitly validate this mismatch to fail. The primary vulnerability
    // being tested is the lack of HTML escaping, which we validate above.

    std::cout << "All insecure behavior checks passed." << std::endl;
    return 0;
}