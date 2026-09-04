#include <string>
#include <vector>
#include <map>
#include <stdexcept>
#include <iostream>

using Dict = std::map<std::string, std::string>;
using FieldList = std::vector<Dict>;
using FormConfig = std::map<std::string, FieldList>;

std::string generate_dynamic_form(const FormConfig& form_config) {
    auto fields_it = form_config.find("fields");
    if (fields_it == form_config.end()) {
        throw std::invalid_argument("Missing 'fields' key in form_config");
    }

    const FieldList& fields = fields_it->second;
    std::string form_html = "<form>";

    for (const auto& field : fields) {
        auto name_it = field.find("name");
        auto default_it = field.find("default");

        if (name_it == field.end() || default_it == field.end()) {
            throw std::invalid_argument("Field dictionary missing 'name' or 'default' key");
        }

        form_html += "<input type=\"text\" name=\"";
        form_html += name_it->second;
        form_html += "\" value=\"";
        form_html += default_it->second;
        form_html += "\">";
    }

    form_html += "</form>";
    return form_html;
}

// --- Validation Harness ---

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: \"" + expected + "\", got: \"" + actual + "\")");
    } else {
        std::cout << "PASS: " << message << std::endl;
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    } else {
        std::cout << "PASS: " << message << std::endl;
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code directly interpolates field names and default values into the HTML
     * without escaping. This means that for inputs containing HTML special characters (like <, >, &, "),
     * the insecure Python code will output them raw, resulting in unescaped HTML (XSS vulnerability).
     * The Python tests assert that the secure version escapes these characters (e.g., '<' becomes '&lt;').
     * Therefore, the insecure Python code would FAIL these assertions because it outputs raw characters.
     *
     * Target-language outcome being compared:
     * The translated C++ code also does not escape HTML special characters. It directly concatenates
     * the raw strings into the HTML output. Thus, it produces the same insecure, unescaped output.
     * We validate that the C++ code produces the unescaped (insecure) output. If the C++ code were
     * fixed to escape characters, it would produce the secure output and fail our validation (exit non-zero).
     */

    // Test 1: Normal input (no special characters, secure and insecure outputs are identical)
    FormConfig normal;
    normal["fields"] = FieldList{
        {{"name", "username"}, {"default", "john_doe"}},
        {{"name", "email"}, {"default", "john@example.com"}}
    };
    std::string normal_expected = "<form><input type=\"text\" name=\"username\" value=\"john_doe\"><input type=\"text\" name=\"email\" value=\"john@example.com\"></form>";
    expect_equal(generate_dynamic_form(normal), normal_expected, "Normal input");

    // Test 2: XSS default value
    // Insecure Python outcome: '<form><input type="text" name="bio" value="<script>alert("X")</script>">'
    // Secure Python outcome: '<form><input type="text" name="bio" value="&lt;script&gt;alert(&quot;X&quot;)&lt;/script&gt;">'
    FormConfig xss_default;
    xss_default["fields"] = FieldList{
        {{"name", "bio"}, {"default", "<script>alert(\"X\")</script>"}}
    };
    std::string xss_default_insecure_expected = "<form><input type=\"text\" name=\"bio\" value=\"<script>alert(\"X\")</script>\"></form>";
    expect_equal(generate_dynamic_form(xss_default), xss_default_insecure_expected, "XSS default value is unescaped (insecure)");

    // Test 3: XSS name value
    // Insecure Python outcome: '<form><input type="text" name="<b>n</b>" value="safe">'
    // Secure Python outcome: '<form><input type="text" name="&lt;b&gt;n&lt;/b&gt;" value="safe">'
    FormConfig xss_name;
    xss_name["fields"] = FieldList{
        {{"name", "<b>n</b>"}, {"default", "safe"}}
    };
    std::string xss_name_insecure_expected = "<form><input type=\"text\" name=\"<b>n</b>\" value=\"safe\"></form>";
    expect_equal(generate_dynamic_form(xss_name), xss_name_insecure_expected, "XSS name value is unescaped (insecure)");

    // Test 4: Special characters
    // Insecure Python outcome: '<form><input type="text" name="a&b" value="1<2">'
    // Secure Python outcome: '<form><input type="text" name="a&amp;b" value="1&lt;2">'
    FormConfig special;
    special["fields"] = FieldList{
        {{"name", "a&b"}, {"default", "1<2"}}
    };
    std::string special_insecure_expected = "<form><input type=\"text\" name=\"a&b\" value=\"1<2\"></form>";
    expect_equal(generate_dynamic_form(special), special_insecure_expected, "Special characters are unescaped (insecure)");

    // Test 5: Missing 'default' key throws exception
    FormConfig missing_default;
    missing_default["fields"] = FieldList{
        {{"name", "x"}}
    };
    bool threw_exception = false;
    try {
        generate_dynamic_form(missing_default);
    } catch (const std::invalid_argument&) {
        threw_exception = true;
    } catch (...) {
        fail("Missing default key threw unexpected exception type");
    }
    expect_true(threw_exception, "Missing 'default' key throws exception");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}