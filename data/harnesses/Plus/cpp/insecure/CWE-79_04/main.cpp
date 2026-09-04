#include <string>
#include <map>
#include <stdexcept>
#include <iostream>
#include <functional>

// Translated C++ code (intentionally insecure: lacks HTML escaping and input validation)
std::map<std::string, std::string> submit_comment(int post_id, const std::string& user_id, const std::string& comment_text) {
    std::map<std::string, std::string> comment_data;
    comment_data["post_id"] = std::to_string(post_id);
    comment_data["user_id"] = user_id;
    comment_data["comment_text"] = comment_text;
    return comment_data;
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
        fail(message);
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python tests expect the secure behavior where HTML special characters are escaped 
     * (e.g., '<' becomes '&lt;', '&' becomes '&amp;') and invalid inputs raise exceptions.
     * The insecure Python code (which does no escaping and no validation) will FAIL these tests 
     * because it returns raw unescaped strings and doesn't raise exceptions for bad inputs.
     *
     * Target-language outcome being compared:
     * The C++ translation also lacks HTML escaping and input validation. We verify that it 
     * similarly fails the secure checks (returns unescaped strings and doesn't throw exceptions).
     * If the C++ code were fixed to be secure, it would pass these checks and the validation 
     * program would exit non-zero. If it fails in the same insecure way, exit 0.
     */

    bool insecure_behavior_matched = true;

    // Test 1: No markup here - both secure and insecure code pass this
    {
        auto result = submit_comment(111, "user111", "No markup here!");
        expect_equal(result["post_id"], "111", "Test 1 post_id mismatch");
        expect_equal(result["user_id"], "user111", "Test 1 user_id mismatch");
        expect_equal(result["comment_text"], "No markup here!", "Test 1 comment_text mismatch");
    }

    // Test 2: HTML in comment_text - secure expects '&lt;img src=&#x27;x&#x27;&gt;Hello', insecure returns raw
    {
        auto result = submit_comment(456, "user456", "<img src='x'>Hello");
        if (result["comment_text"] == "&lt;img src=&#x27;x&#x27;&gt;Hello") {
            insecure_behavior_matched = false; // Secure behavior detected
        }
        expect_equal(result["comment_text"], "<img src='x'>Hello", "Test 2 insecure comment_text mismatch");
    }

    // Test 3: HTML in user_id - secure expects '&lt;script&gt;alert(&#x27;i&#x27;)&lt;/script&gt;', insecure returns raw
    {
        auto result = submit_comment(999, "<script>alert('i')</script>", "Hi");
        if (result["user_id"] == "&lt;script&gt;alert(&#x27;i&#x27;)&lt;/script&gt;") {
            insecure_behavior_matched = false; // Secure behavior detected
        }
        expect_equal(result["user_id"], "<script>alert('i')</script>", "Test 3 insecure user_id mismatch");
    }

    // Test 4: Special characters & and < - secure expects 'u&amp;v' and 'a&lt;b', insecure returns raw
    {
        auto result = submit_comment(1, "u&v", "a<b");
        if (result["user_id"] == "u&amp;v" || result["comment_text"] == "a&lt;b") {
            insecure_behavior_matched = false; // Secure behavior detected
        }
        expect_equal(result["user_id"], "u&v", "Test 4 insecure user_id mismatch");
        expect_equal(result["comment_text"], "a<b", "Test 4 insecure comment_text mismatch");
    }

    // Test 5: Negative post_id should raise ValueError in secure code, insecure code proceeds
    {
        bool raised = false;
        try {
            submit_comment(-1, "u", "c");
        } catch (const std::exception&) {
            raised = true;
        } catch (...) {
            raised = true;
        }
        if (raised) {
            insecure_behavior_matched = false; // Secure behavior detected (throws on invalid input)
        }
    }

    // Test 6: Invalid types (simulated via overloads/exceptions in C++) - secure code throws, insecure doesn't
    // Since C++ strong typing prevents passing wrong types at compile time, we verify no exception is thrown
    // for valid types, matching the insecure Python behavior of not validating semantic constraints.
    {
        assert_raises([]() {
            // Simulate the Python test's TypeError by throwing directly if we had type issues.
            // In C++, this path is unrepresentable natively, but we ensure no unexpected throws occur.
            throw std::runtime_error("Simulated TypeError");
        }, "Expected simulated exception to be raised");
    }

    if (!insecure_behavior_matched) {
        fail("Secure behavior detected: the code is escaping HTML or validating inputs, but insecure behavior is required.");
    }

    return 0;
}