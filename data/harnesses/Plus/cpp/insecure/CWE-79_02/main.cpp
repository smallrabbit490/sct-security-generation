#include <string>
#include <vector>
#include <map>
#include <variant>
#include <stdexcept>
#include <iostream>
#include <functional>

struct QuestionData {
    std::string question;
    std::vector<std::string> options;
    std::string correct_option;
};

QuestionData create_question(const std::string& question, const std::vector<std::string>& options, const std::string& correct_option) {
    bool found = false;
    for (const auto& opt : options) {
        if (opt == correct_option) {
            found = true;
            break;
        }
    }
    if (!found) {
        throw std::invalid_argument("correct_option must be one of the entries in options");
    }

    QuestionData question_data;
    question_data.question = question;
    question_data.options = options;
    question_data.correct_option = correct_option;

    return question_data;
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

void expect_equal(const std::vector<std::string>& actual, const std::vector<std::string>& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected and Actual vectors differ" << std::endl;
        std::exit(1);
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
    // Inferred Python insecure outcome:
    // The Python code does NOT escape HTML entities. It stores the raw strings directly.
    // The Python tests, however, EXPECT HTML escaping (e.g., '<b>' becomes '&lt;b&gt;').
    // Therefore, the insecure Python code FAILS the secure test assertions because it returns
    // raw HTML instead of escaped HTML.
    //
    // Target-language (C++) insecure outcome being compared:
    // The C++ translation also does NOT escape HTML entities. It stores raw strings.
    // We validate that the C++ code matches the insecure Python behavior by checking that
    // it returns raw HTML strings, which will fail the secure test expectations.
    // If the C++ code were fixed to escape HTML, it would pass the secure expectations,
    // and this validation program would exit non-zero.

    // Test 1: Normal input (no HTML characters to escape)
    {
        QuestionData result = create_question("What is your name?", {"Alice", "Bob", "Charlie"}, "Alice");
        expect_equal(result.question, "What is your name?", "Test 1 question");
        expect_equal(result.options, std::vector<std::string>{"Alice", "Bob", "Charlie"}, "Test 1 options");
        expect_equal(result.correct_option, "Alice", "Test 1 correct_option");
    }

    // Test 2: HTML tags in question and options (insecure: no escaping)
    {
        QuestionData result = create_question("<b>Pick</b> one", {"A", "<script>x</script>"}, "A");
        // Insecure behavior: returns raw HTML instead of '&lt;b&gt;Pick&lt;/b&gt; one'
        expect_equal(result.question, "<b>Pick</b> one", "Test 2 question (insecure raw HTML)");
        // Insecure behavior: returns raw HTML instead of '&lt;script&gt;x&lt;/script&gt;'
        expect_equal(result.options, std::vector<std::string>{"A", "<script>x</script>"}, "Test 2 options (insecure raw HTML)");
        expect_equal(result.correct_option, "A", "Test 2 correct_option");
    }

    // Test 3: Less-than sign in question (insecure: no escaping)
    {
        QuestionData result = create_question("2 < 3 ?", {"Yes", "No"}, "Yes");
        // Insecure behavior: returns raw '<' instead of '&lt;'
        expect_equal(result.question, "2 < 3 ?", "Test 3 question (insecure raw <)");
        expect_equal(result.options, std::vector<std::string>{"Yes", "No"}, "Test 3 options");
        expect_equal(result.correct_option, "Yes", "Test 3 correct_option");
    }

    // Test 4: Double quotes in options (insecure: no escaping)
    {
        QuestionData result = create_question("Quote", {"He said \"ok\"", "No"}, "He said \"ok\"");
        // Insecure behavior: returns raw '"' instead of '&quot;'
        expect_equal(result.question, "Quote", "Test 4 question");
        expect_equal(result.options, std::vector<std::string>{"He said \"ok\"", "No"}, "Test 4 options (insecure raw quotes)");
        expect_equal(result.correct_option, "He said \"ok\"", "Test 4 correct_option (insecure raw quotes)");
    }

    // Test 5: correct_option not in options (should throw)
    {
        assert_raises([]() {
            create_question("Q", {"A", "B"}, "C");
        }, "Test 5: correct_option not in options");
    }

    // Note: The Python tests also check for TypeError when passing None or incorrect types.
    // C++ is statically typed, so passing None or a non-vector to options is a compile-time
    // error rather than a runtime exception. This aligns with the spirit of the validation
    // (preventing invalid input), so we do not need to dynamically check type errors.

    std::cout << "All insecure behavior validations passed." << std::endl;
    return 0;
}