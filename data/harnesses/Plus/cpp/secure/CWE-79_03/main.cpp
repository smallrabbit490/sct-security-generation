#include <string>
#include <map>
#include <stdexcept>
#include <iostream>
#include <cstdlib>

std::string html_escape(const std::string& input) {
    std::string output;
    output.reserve(input.size());
    for (char c : input) {
        switch (c) {
            case '&':  output += "&amp;"; break;
            case '<':  output += "&lt;"; break;
            case '>':  output += "&gt;"; break;
            case '"':  output += "&quot;"; break;
            case '\'': output += "&#x27;"; break;
            default:   output += c; break;
        }
    }
    return output;
}

std::map<std::string, std::string> create_article(const std::string& title, const std::string& content) {
    return {
        {"title", html_escape(title)},
        {"content", html_escape(content)}
    };
}

// Overloads to reject non-string types (simulating Python's TypeError for None, int, dict, etc.)
std::map<std::string, std::string> create_article(std::nullptr_t, const std::string&) {
    throw std::invalid_argument("title and content must be strings");
}

std::map<std::string, std::string> create_article(const std::string&, std::nullptr_t) {
    throw std::invalid_argument("title and content must be strings");
}

std::map<std::string, std::string> create_article(int, const std::string&) {
    throw std::invalid_argument("title and content must be strings");
}

std::map<std::string, std::string> create_article(const std::string&, int) {
    throw std::invalid_argument("title and content must be strings");
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
        std::cerr << "  Expected: " << expected << std::endl;
        std::cerr << "  Actual:   " << actual << std::endl;
        std::exit(1);
    }
}

template <typename Func>
void assert_raises(Func func, const std::string& message) {
    bool raised = false;
    try {
        func();
    } catch (const std::invalid_argument&) {
        raised = true;
    } catch (const std::exception&) {
        fail(message + " - unexpected exception type thrown");
    }
    if (!raised) {
        fail(message + " - expected an exception but none was raised");
    }
}

int main() {
    // Test 1: Basic strings without special characters
    {
        auto result = create_article("Golden Retriever", "Golden Retrievers are cute.");
        expect_equal(result["title"], "Golden Retriever", "Test 1 title");
        expect_equal(result["content"], "Golden Retrievers are cute.", "Test 1 content");
    }

    // Test 2: Strings with HTML tags and single quotes
    {
        auto result = create_article("An <strong>Important</strong> Announcement", "Please be aware of <script>alert('x')</script>.");
        expect_equal(result["title"], "An &lt;strong&gt;Important&lt;/strong&gt; Announcement", "Test 2 title");
        expect_equal(result["content"], "Please be aware of &lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;.", "Test 2 content");
    }

    // Test 3: Strings with ampersand and greater-than
    {
        auto result = create_article("A & B", "C > D");
        expect_equal(result["title"], "A &amp; B", "Test 3 title");
        expect_equal(result["content"], "C &gt; D", "Test 3 content");
    }

    // Test 4: Strings with double quotes
    {
        auto result = create_article("He said \"ok\"", "Done");
        expect_equal(result["title"], "He said &quot;ok&quot;", "Test 4 title");
        expect_equal(result["content"], "Done", "Test 4 content");
    }

    // Test 5: nullptr title should throw
    assert_raises([]() { create_article(nullptr, "x"); }, "Test 5: nullptr title should throw");

    // Test 6: nullptr content should throw
    assert_raises([]() { create_article("x", nullptr); }, "Test 6: nullptr content should throw");

    // Test 7: int title should throw
    assert_raises([]() { create_article(1, "x"); }, "Test 7: int title should throw");

    // Test 8: int content should throw
    assert_raises([]() { create_article("x", 1); }, "Test 8: int content should throw");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}