#include <string>
#include <vector>
#include <stdexcept>
#include <sstream>
#include <iostream>
#include <functional>

// HTML escaping function to prevent XSS (CWE-79)
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

// Main entry point function
std::string render_marked_search_results(const std::string& query, const std::vector<std::string>& results) {
    std::string safe_query = html_escape(query);

    std::ostringstream items_stream;
    for (const auto& t : results) {
        items_stream << "<li>" << html_escape(t) << "</li>";
    }

    return "<div class=\"q\">Results for: <span class=\"query\">" + safe_query +
           "</span></div><ul>" + items_stream.str() + "</ul>";
}

// Overloads to test type checking (mimicking Python's TypeError for wrong types)
std::string render_marked_search_results(const std::string&, const std::string&) {
    throw std::invalid_argument("results must be a list");
}

std::string render_marked_search_results(const std::string&, const std::vector<int>&) {
    throw std::invalid_argument("each result title must be a string");
}

std::string render_marked_search_results(int, const std::vector<std::string>&) {
    throw std::invalid_argument("query must be a string");
}

std::string render_marked_search_results(int, const std::string&) {
    throw std::invalid_argument("query must be a string and results must be a list");
}

std::string render_marked_search_results(int, const std::vector<int>&) {
    throw std::invalid_argument("query must be a string and each result title must be a string");
}

// Test helpers
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
        fail(message + " (expected: \"" + expected + "\", got: \"" + actual + "\")");
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

bool string_contains(const std::string& haystack, const std::string& needle) {
    return haystack.find(needle) != std::string::npos;
}

bool ends_with(const std::string& str, const std::string& suffix) {
    if (suffix.size() > str.size()) return false;
    return std::equal(suffix.rbegin(), suffix.rend(), str.rbegin());
}

// Test suite
void check() {
    // Test 1: Basic functionality
    std::string out = render_marked_search_results(std::string("python"), std::vector<std::string>{"Intro", "Advanced"});
    expect_true(string_contains(out, "<span class=\"query\">python</span>"), "Query span missing or incorrect");
    expect_true(string_contains(out, "<li>Intro</li>"), "First list item missing or incorrect");
    expect_true(string_contains(out, "<li>Advanced</li>"), "Second list item missing or incorrect");

    // Test 2: Escaping malicious inputs
    std::string out2 = render_marked_search_results(
        std::string("<img src=x onerror=alert(1)>"),
        std::vector<std::string>{"<script>alert(1)</script>", "A \"quote\" & B"}
    );
    expect_true(!string_contains(out2, "<script>"), "Unescaped <script> found in output");
    expect_true(!string_contains(out2, "<img"), "Unescaped <img found in output");
    expect_true(string_contains(out2, "&lt;script&gt;alert(1)&lt;/script&gt;"), "Script tag not escaped correctly");
    expect_true(string_contains(out2, "A &quot;quote&quot; &amp; B"), "Quotes and ampersand not escaped correctly");
    expect_true(string_contains(out2, "&lt;img src=x onerror=alert(1)&gt;"), "Img tag not escaped correctly");

    // Test 3: Empty query and results
    std::string out3 = render_marked_search_results(std::string(""), std::vector<std::string>{});
    expect_true(string_contains(out3, "Results for: <span class=\"query\"></span>"), "Empty query span missing or incorrect");
    expect_true(ends_with(out3, "</ul>"), "Output does not end with </ul>");

    // Test 4: Type checks (simulating Python's TypeError)
    assert_raises([]() {
        render_marked_search_results(0, std::vector<std::string>{"ok"});
    }, "Query as int should raise exception");

    assert_raises([]() {
        render_marked_search_results(std::string("q"), std::string("not-a-list"));
    }, "Results as string should raise exception");

    assert_raises([]() {
        render_marked_search_results(std::string("q"), std::vector<int>{1});
    }, "Results as list of ints should raise exception");
}

int main() {
    check();
    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }
    std::cout << "All tests passed." << std::endl;
    return 0;
}