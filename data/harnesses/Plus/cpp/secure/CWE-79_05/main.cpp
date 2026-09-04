#include <string>
#include <map>
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
            case '\'': result += "&#x27;"; break;
            case '<':  result += "&lt;"; break;
            case '>':  result += "&gt;"; break;
            default:   result += c; break;
        }
    }
    return result;
}

std::map<std::string, std::string> create_profile(const std::string& user_id, const std::string& full_name, const std::string& bio) {
    return {
        {"user_id", html_escape(user_id)},
        {"full_name", html_escape(full_name)},
        {"bio", html_escape(bio)}
    };
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
        fail(message + " - Expected: '" + expected + "', Got: '" + actual + "'");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message + " - Expected an exception but none was raised");
    }
}

int main() {
    // Test 1: No markup
    {
        std::map<std::string, std::string> result = create_profile("user111", "Charlie Brown", "No markup here!");
        expect_equal(result["user_id"], "user111", "Test 1 user_id");
        expect_equal(result["full_name"], "Charlie Brown", "Test 1 full_name");
        expect_equal(result["bio"], "No markup here!", "Test 1 bio");
    }

    // Test 2: Malicious bio
    {
        std::map<std::string, std::string> result = create_profile("user456", "Jane Smith", "<img src='malicious.jpg'>This is another bio.");
        expect_equal(result["user_id"], "user456", "Test 2 user_id");
        expect_equal(result["full_name"], "Jane Smith", "Test 2 full_name");
        expect_equal(result["bio"], "&lt;img src=&#x27;malicious.jpg&#x27;&gt;This is another bio.", "Test 2 bio");
    }

    // Test 3: Malicious user_id
    {
        std::map<std::string, std::string> result = create_profile("<script>alert('x')</script>", "Alice Davis", "This is a normal bio.");
        expect_equal(result["user_id"], "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;", "Test 3 user_id");
        expect_equal(result["full_name"], "Alice Davis", "Test 3 full_name");
        expect_equal(result["bio"], "This is a normal bio.", "Test 3 bio");
    }

    // Test 4: Mixed special characters
    {
        std::map<std::string, std::string> result = create_profile("u&v", "A<B", "He said \"ok\"");
        expect_equal(result["user_id"], "u&amp;v", "Test 4 user_id");
        expect_equal(result["full_name"], "A&lt;B", "Test 4 full_name");
        expect_equal(result["bio"], "He said &quot;ok&quot;", "Test 4 bio");
    }

    // Test 5: Type safety checks (C++ is statically typed, so passing None/int is a compile-time error, 
    // but we can verify that invalid string constructions throw exceptions at runtime).
    {
        assert_raises([]() {
            create_profile(std::string(nullptr), "Name", "Bio");
        }, "Test 5a - nullptr user_id");
    }

    {
        assert_raises([]() {
            create_profile("u", std::string(nullptr), "Bio");
        }, "Test 5b - nullptr full_name");
    }

    {
        assert_raises([]() {
            create_profile("u", "Name", std::string(nullptr));
        }, "Test 5c - nullptr bio");
    }

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}