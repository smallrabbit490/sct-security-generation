#include <string>
#include <vector>
#include <map>
#include <stdexcept>
#include <functional>
#include <iostream>

using Dict = std::map<std::string, std::string>;
using FieldList = std::vector<Dict>;
using FormConfig = std::map<std::string, FieldList>;

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

std::string generate_dynamic_form(const FormConfig& form_config) {
    if (form_config.find("fields") == form_config.end()) {
        throw std::invalid_argument("form_config must be a dict with 'fields'");
    }
    const FieldList& fields = form_config.at("fields");

    std::string form_html = "<form>";
    for (const auto& field : fields) {
        if (field.find("name") == field.end() || field.find("default") == field.end()) {
            throw std::invalid_argument("each field must be a dict with 'name' and 'default'");
        }
        const std::string& name = field.at("name");
        const std::string& default_val = field.at("default");

        std::string safe_name = html_escape(name);
        std::string safe_default = html_escape(default_val);

        form_html += "<input type=\"text\" name=\"" + safe_name + "\" value=\"" + safe_default + "\">";
    }
    form_html += "</form>";
    return form_html;
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
        fail(message + " - Expected: '" + expected + "', Got: '" + actual + "'");
    }
}

void assert_raises(std::function<void()> func, const std::string& message) {
    try {
        func();
    } catch (const std::exception&) {
        return;
    }
    fail("Expected exception but none was thrown: " + message);
}

int main() {
    // Test missing 'fields' key
    FormConfig missing_fields;
    assert_raises([&]() { generate_dynamic_form(missing_fields); }, "Missing 'fields' key test");

    // Test missing 'default' key
    FormConfig missing_default;
    missing_default["fields"] = FieldList{Dict{{"name", "test"}}};
    assert_raises([&]() { generate_dynamic_form(missing_default); }, "Missing 'default' key test");

    // Test missing 'name' key
    FormConfig missing_name;
    missing_name["fields"] = FieldList{Dict{{"default", "test"}}};
    assert_raises([&]() { generate_dynamic_form(missing_name); }, "Missing 'name' key test");

    // Test normal valid config
    FormConfig valid_config;
    valid_config["fields"] = FieldList{
        Dict{{"name", "username"}, {"default", "john_doe"}},
        Dict{{"name", "email"}, {"default", "john@example.com"}}
    };
    std::string result = generate_dynamic_form(valid_config);
    expect_equal(result, "<form><input type=\"text\" name=\"username\" value=\"john_doe\"><input type=\"text\" name=\"email\" value=\"john@example.com\"></form>", "Normal valid config test");

    // Test XSS default value
    FormConfig xss_config;
    xss_config["fields"] = FieldList{Dict{{"name", "bio"}, {"default", "<script>alert(\"X\")</script>"}}};
    std::string xss_result = generate_dynamic_form(xss_config);
    expect_equal(xss_result, "<form><input type=\"text\" name=\"bio\" value=\"&lt;script&gt;alert(&quot;X&quot;)&lt;/script&gt;\"></form>", "XSS default value test");

    // Test XSS name value
    FormConfig xss_name_config;
    xss_name_config["fields"] = FieldList{Dict{{"name", "<b>n</b>"}, {"default", "safe"}}};
    std::string xss_name_result = generate_dynamic_form(xss_name_config);
    expect_equal(xss_name_result, "<form><input type=\"text\" name=\"&lt;b&gt;n&lt;/b&gt;\" value=\"safe\"></form>", "XSS name value test");

    // Test special characters
    FormConfig amp_config;
    amp_config["fields"] = FieldList{Dict{{"name", "a&b"}, {"default", "1<2"}}};
    std::string amp_result = generate_dynamic_form(amp_config);
    expect_equal(amp_result, "<form><input type=\"text\" name=\"a&amp;b\" value=\"1&lt;2\"></form>", "Special characters test");

    return 0;
}