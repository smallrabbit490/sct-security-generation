#include <string>
#include <unordered_map>
#include <stdexcept>
#include <sstream>
#include <iostream>
#include <cstdlib>

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
            default:   buffer.append(1, data[pos]); break;
        }
    }
    return buffer;
}

std::string render_email_template(const std::string& template_str, const std::unordered_map<std::string, std::string>& data) {
    std::string rendered_template = template_str;
    for (const auto& pair : data) {
        const std::string& key = pair.first;
        const std::string& value = pair.second;
        
        if (key.empty()) {
            throw std::invalid_argument("keys must be non-empty strings");
        }
        
        std::string placeholder = "{{" + key + "}}";
        
        std::ostringstream oss;
        oss << value;
        std::string sanitized_value = html_escape(oss.str());
        
        size_t pos = 0;
        while ((pos = rendered_template.find(placeholder, pos)) != std::string::npos) {
            rendered_template.replace(pos, placeholder.length(), sanitized_value);
            pos += sanitized_value.length();
        }
    }
    return rendered_template;
}

// Test helpers
int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
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

template <typename F>
void assert_raises(F callable_obj, const std::string& message) {
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
    // Test 1: Basic replacement with multiple placeholders
    expect_equal(
        render_email_template("Dear {{customer_name}}, your balance is {{balance}} USD.", {{"customer_name", "Jane"}, {"balance", "1000"}}),
        "Dear Jane, your balance is 1000 USD.",
        "Test 1: Basic replacement"
    );

    // Test 2: Another basic replacement
    expect_equal(
        render_email_template("Hello, {{name}}! Your order {{order_id}} has been shipped.", {{"name", "Tom"}, {"order_id", "12345"}}),
        "Hello, Tom! Your order 12345 has been shipped.",
        "Test 2: Another basic replacement"
    );

    // Test 3: HTML escaping for XSS prevention
    expect_equal(
        render_email_template("Hi, {{customer_name}}!", {{"customer_name", "<h1>Bob</h1>"}}),
        "Hi, &lt;h1&gt;Bob&lt;/h1&gt;!",
        "Test 3: HTML escaping"
    );

    // Test 4: Ampersand escaping and multiple occurrences of the same placeholder
    expect_equal(
        render_email_template("X={{x}}, X again={{x}}.", {{"x", "A&B"}}),
        "X=A&amp;B, X again=A&amp;B.",
        "Test 4: Ampersand escaping and multiple occurrences"
    );

    // Test 5: No placeholders in template
    expect_equal(
        render_email_template("No placeholders.", {{"x", "1"}}),
        "No placeholders.",
        "Test 5: No placeholders"
    );

    // Test 6: Placeholder replaced with empty string
    expect_equal(
        render_email_template("{{k}}", {{"k", ""}}),
        "",
        "Test 6: Empty string replacement"
    );

    // Test 7: Empty template
    expect_equal(
        render_email_template("", {{"k", "v"}}),
        "",
        "Test 7: Empty template"
    );

    // Test 8: Empty data map
    expect_equal(
        render_email_template("Hello {{name}}", {}),
        "Hello {{name}}",
        "Test 8: Empty data map"
    );

    // Test 9: Exception on empty key in data map
    assert_raises([]() {
        render_email_template("Hi {{a}}", {{"", "x"}});
    }, "Expected an exception for empty key but none was raised");

    // Test 10: Exception on another empty key case
    assert_raises([]() {
        render_email_template("Hi", {{"", "y"}});
    }, "Expected an exception for empty key in map but none was raised");

    if (fail_count > 0) {
        std::cerr << fail_count << " test(s) failed." << std::endl;
        return 1;
    }

    return 0;
}