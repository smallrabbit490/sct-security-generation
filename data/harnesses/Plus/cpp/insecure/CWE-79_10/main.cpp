#include <string>
#include <vector>
#include <stdexcept>
#include <iostream>

// Translated C++ code (insecure version)
std::string render_marked_search_results(const std::string& query, const std::vector<std::string>& results) {
    // Unsafe: directly embeds user input into HTML
    std::string items;
    for (const auto& t : results) {
        items += "<li>" + t + "</li>";
    }
    return "<div class=\"q\">Results for: <span class=\"query\">" + query + "</span></div><ul>" + items + "</ul>";
}

// Validation helpers
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_in(const std::string& haystack, const std::string& needle, const std::string& message) {
    if (haystack.find(needle) == std::string::npos) {
        fail(message + " (expected to find '" + needle + "' in '" + haystack + "')");
    }
}

void expect_not_in(const std::string& haystack, const std::string& needle, const std::string& message) {
    if (haystack.find(needle) != std::string::npos) {
        fail(message + " (expected NOT to find '" + needle + "' in '" + haystack + "')");
    }
}

// Inferred Python insecure outcome:
// The insecure Python code fails the secure test checks because it does NOT escape HTML
// special characters. Specifically, it will:
// 1. Leave "<script>" unescaped in the output.
// 2. Leave "<img" unescaped in the output.
// 3. Fail to produce "&lt;script&gt;alert(1)&lt;/script&gt;".
// 4. Fail to produce "A &quot;quote&quot; &amp; B".
// 5. Fail to produce "&lt;img src=x onerror=alert(1)&gt;".
// The Python tests assert that these escaped strings MUST be present and unescaped tags
// MUST be absent. The insecure code violates these assertions.

// Target-language outcome being compared:
// We check if the C++ translation exhibits the same insecure behavior (failing to escape).
// If the C++ code is insecure (like the Python original), it will produce unescaped output,
// causing our validation checks for the escaped strings to fail (which we treat as success here).
// If the C++ code is secure (escapes properly), it will pass the escaped string checks,
// and our validation program will exit non-zero, indicating the vulnerability was fixed.

int main() {
    // Test 1: Basic functionality
    std::string out = render_marked_search_results("python", {"Intro", "Advanced"});
    expect_in(out, "<span class=\"query\">python</span>", "Basic query span missing");
    expect_in(out, "<li>Intro</li>", "Basic item 1 missing");
    expect_in(out, "<li>Advanced</li>", "Basic item 2 missing");

    // Test 2: XSS / HTML escaping checks
    std::string out2 = render_marked_search_results("<img src=x onerror=alert(1)>", {"<script>alert(1)</script>", "A \"quote\" & B"});

    // Check if the code is insecure (unescaped tags are present)
    bool has_unescaped_script = (out2.find("<script>") != std::string::npos);
    bool has_unescaped_img = (out2.find("<img") != std::string::npos);

    // Check if the code is secure (escaped tags are present)
    bool has_escaped_script = (out2.find("&lt;script&gt;alert(1)&lt;/script&gt;") != std::string::npos);
    bool has_escaped_quote_amp = (out2.find("A &quot;quote&quot; &amp; B") != std::string::npos);
    bool has_escaped_img = (out2.find("&lt;img src=x onerror=alert(1)&gt;") != std::string::npos);

    // If the code is secure, it will have the escaped strings and lack unescaped ones.
    // We want the validation to succeed (exit 0) ONLY if the code is INSECURE.
    if (has_escaped_script && has_escaped_quote_amp && has_escaped_img && !has_unescaped_script && !has_unescaped_img) {
        fail("Vulnerability is fixed: output is properly escaped.");
    }

    // If the code is insecure, it will lack the escaped strings and/or have unescaped ones.
    // This matches the expected insecure Python outcome.
    if (!has_escaped_script || !has_escaped_quote_amp || !has_escaped_img || has_unescaped_script || has_unescaped_img) {
        // Insecure behavior confirmed, matching the Python original.
        return 0;
    }

    fail("Unexpected state: output is neither fully secure nor insecure in the expected manner.");
    return 1;
}