#include <string>
#include <map>
#include <stdexcept>
#include <iostream>

std::string html_escape(const std::string& data) {
    std::string escaped;
    escaped.reserve(data.size());
    for (char c : data) {
        switch (c) {
            case '&':  escaped.append("&amp;");  break;
            case '\"': escaped.append("&quot;"); break;
            case '\'': escaped.append("&#x27;"); break;
            case '<':  escaped.append("&lt;");   break;
            case '>':  escaped.append("&gt;");   break;
            default:   escaped.push_back(c);     break;
        }
    }
    return escaped;
}

std::map<std::string, std::string> submit_comment(int post_id, const std::string& user_id, const std::string& comment_text) {
    if (post_id < 0) {
        throw std::invalid_argument("post_id must be non-negative");
    }

    std::map<std::string, std::string> result;
    result["post_id"] = std::to_string(post_id);
    result["user_id"] = html_escape(user_id);
    result["comment_text"] = html_escape(comment_text);

    return result;
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
void assert_raises(Func callable_obj, const std::string& exc_type_name) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail("Expected an exception of type " + exc_type_name + " but none was raised");
    }
}

int main() {
    // Test 1: No markup
    {
        std::map<std::string, std::string> result = submit_comment(111, "user111", "No markup here!");
        expect_equal(result["post_id"], "111", "Test 1 post_id");
        expect_equal(result["user_id"], "user111", "Test 1 user_id");
        expect_equal(result["comment_text"], "No markup here!", "Test 1 comment_text");
    }

    // Test 2: HTML tags and quotes in comment_text
    {
        std::map<std::string, std::string> result = submit_comment(456, "user456", "<img src='x'>Hello");
        expect_equal(result["post_id"], "456", "Test 2 post_id");
        expect_equal(result["user_id"], "user456", "Test 2 user_id");
        expect_equal(result["comment_text"], "&lt;img src=&#x27;x&#x27;&gt;Hello", "Test 2 comment_text");
    }

    // Test 3: HTML tags and quotes in user_id
    {
        std::map<std::string, std::string> result = submit_comment(999, "<script>alert('i')</script>", "Hi");
        expect_equal(result["post_id"], "999", "Test 3 post_id");
        expect_equal(result["user_id"], "&lt;script&gt;alert(&#x27;i&#x27;)&lt;/script&gt;", "Test 3 user_id");
        expect_equal(result["comment_text"], "Hi", "Test 3 comment_text");
    }

    // Test 4: Ampersand and less-than
    {
        std::map<std::string, std::string> result = submit_comment(1, "u&v", "a<b");
        expect_equal(result["post_id"], "1", "Test 4 post_id");
        expect_equal(result["user_id"], "u&amp;v", "Test 4 user_id");
        expect_equal(result["comment_text"], "a&lt;b", "Test 4 comment_text");
    }

    // Test 5: Negative post_id (ValueError equivalent -> std::invalid_argument/logic_error)
    assert_raises([]() { submit_comment(-1, "u", "c"); }, "std::invalid_argument (ValueError)");

    // Note: The Python tests for TypeError on post_id="1", user_id=None, comment_text=None
    // cannot be directly translated because C++ is statically typed and enforces
    // parameter types at compile time. Passing a string or None to an int parameter
    // is a compile-time error in C++, which inherently satisfies the safety check
    // that the Python TypeError was guarding against.

    return 0;
}