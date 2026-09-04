#include <string>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include <iostream>
#include <functional>

// Helper function to mimic Python's html.escape(s, quote=True)
std::string html_escape(const std::string& s) {
    std::string result;
    result.reserve(s.size());
    for (char c : s) {
        switch (c) {
            case '&': result += "&amp;"; break;
            case '<': result += "&lt;"; break;
            case '>': result += "&gt;"; break;
            case '"': result += "&quot;"; break;
            case '\'': result += "&#x27;"; break;
            default: result += c; break;
        }
    }
    return result;
}

struct QuestionDict {
    std::string question;
    std::vector<std::string> options;
    std::string correct_option;
};

bool operator==(const QuestionDict& lhs, const QuestionDict& rhs) {
    return lhs.question == rhs.question &&
           lhs.options == rhs.options &&
           lhs.correct_option == rhs.correct_option;
}

QuestionDict create_question(const std::string& question, const std::vector<std::string>& options, const std::string& correct_option) {
    if (options.empty()) {
        throw std::invalid_argument("options must be a non-empty list");
    }

    if (std::find(options.begin(), options.end(), correct_option) == options.end()) {
        throw std::invalid_argument("correct_option must be in options");
    }

    std::string encoded_question = html_escape(question);

    std::vector<std::string> encoded_options;
    encoded_options.reserve(options.size());
    for (const auto& opt : options) {
        encoded_options.push_back(html_escape(opt));
    }

    std::string encoded_correct = html_escape(correct_option);

    return {encoded_question, encoded_options, encoded_correct};
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

void expect_equal(const QuestionDict& actual, const QuestionDict& expected, const std::string& message) {
    if (!(actual == expected)) {
        fail(message);
    }
}

void assert_raises(std::function<void()> callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    } catch (...) {
        // Expected exception caught (non-standard)
    }
}

int main() {
    // Test 1: Basic valid input
    {
        QuestionDict result = create_question(
            std::string("What is your name?"),
            std::vector<std::string>{"Alice", "Bob", "Charlie"},
            std::string("Alice")
        );
        QuestionDict expected = {
            std::string("What is your name?"),
            std::vector<std::string>{"Alice", "Bob", "Charlie"},
            std::string("Alice")
        };
        expect_equal(result, expected, "Test 1: Basic valid input");
    }

    // Test 2: HTML tags in question and options
    {
        QuestionDict result = create_question(
            std::string("<b>Pick</b> one"),
            std::vector<std::string>{"A", "<script>x</script>"},
            std::string("A")
        );
        QuestionDict expected = {
            std::string("&lt;b&gt;Pick&lt;/b&gt; one"),
            std::vector<std::string>{"A", "&lt;script&gt;x&lt;/script&gt;"},
            std::string("A")
        };
        expect_equal(result, expected, "Test 2: HTML tags in question and options");
    }

    // Test 3: Less-than symbol in question
    {
        QuestionDict result = create_question(
            std::string("2 < 3 ?"),
            std::vector<std::string>{"Yes", "No"},
            std::string("Yes")
        );
        QuestionDict expected = {
            std::string("2 &lt; 3 ?"),
            std::vector<std::string>{"Yes", "No"},
            std::string("Yes")
        };
        expect_equal(result, expected, "Test 3: Less-than symbol in question");
    }

    // Test 4: Double quotes in options
    {
        QuestionDict result = create_question(
            std::string("Quote"),
            std::vector<std::string>{"He said \"ok\"", "No"},
            std::string("He said \"ok\"")
        );
        QuestionDict expected = {
            std::string("Quote"),
            std::vector<std::string>{"He said &quot;ok&quot;", "No"},
            std::string("He said &quot;ok&quot;")
        };
        expect_equal(result, expected, "Test 4: Double quotes in options");
    }

    // Test 5: correct_option not in options (should raise)
    assert_raises([]() {
        create_question(std::string("Q"), std::vector<std::string>{"A", "B"}, std::string("C"));
    }, "Test 5: correct_option not in options");

    // Test 6: Empty options list (should raise)
    assert_raises([]() {
        create_question(std::string("Q"), std::vector<std::string>{}, std::string("A"));
    }, "Test 6: Empty options list");

    // Test 7: Ampersand in question
    {
        QuestionDict result = create_question(
            std::string("A & B"),
            std::vector<std::string>{"Yes"},
            std::string("Yes")
        );
        QuestionDict expected = {
            std::string("A &amp; B"),
            std::vector<std::string>{"Yes"},
            std::string("Yes")
        };
        expect_equal(result, expected, "Test 7: Ampersand in question");
    }

    // Test 8: Single quote in options
    {
        QuestionDict result = create_question(
            std::string("Quote test"),
            std::vector<std::string>{"It's fine", "No"},
            std::string("It's fine")
        );
        QuestionDict expected = {
            std::string("Quote test"),
            std::vector<std::string>{"It&#x27;s fine", "No"},
            std::string("It&#x27;s fine")
        };
        expect_equal(result, expected, "Test 8: Single quote in options");
    }

    // Test 9: Greater-than symbol in correct_option
    {
        QuestionDict result = create_question(
            std::string("Math"),
            std::vector<std::string>{"3 > 2", "False"},
            std::string("3 > 2")
        );
        QuestionDict expected = {
            std::string("Math"),
            std::vector<std::string>{"3 &gt; 2", "False"},
            std::string("3 &gt; 2")
        };
        expect_equal(result, expected, "Test 9: Greater-than symbol in correct_option");
    }

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}