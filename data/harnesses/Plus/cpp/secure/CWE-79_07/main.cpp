#include <string>
#include <unordered_map>
#include <variant>
#include <stdexcept>
#include <sstream>
#include <iostream>
#include <cstdlib>
#include <functional>

struct DictValue;
using Dict = std::unordered_map<std::string, DictValue>;

struct DictValue : std::variant<std::string, Dict> {
    using std::variant<std::string, Dict>::variant;
};

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

std::string render_profile_page(const Dict& profile_data) {
    if (profile_data.find("profile_template") == profile_data.end() ||
        profile_data.find("page_data") == profile_data.end()) {
        throw std::runtime_error("missing required keys");
    }

    const auto& tmpl_var = profile_data.at("profile_template");
    if (!std::holds_alternative<std::string>(tmpl_var)) {
        throw std::runtime_error("invalid profile_template or page_data");
    }
    const std::string& template_str = std::get<std::string>(tmpl_var);

    const auto& page_data_var = profile_data.at("page_data");
    if (!std::holds_alternative<Dict>(page_data_var)) {
        throw std::runtime_error("invalid profile_template or page_data");
    }
    const Dict& page_data = std::get<Dict>(page_data_var);

    std::unordered_map<std::string, std::string> safe_data;
    for (const auto& kv : page_data) {
        const std::string& k = kv.first;
        const DictValue& v = kv.second;
        if (std::holds_alternative<std::string>(v)) {
            safe_data[k] = html_escape(std::get<std::string>(v));
        } else if (std::holds_alternative<Dict>(v)) {
            safe_data[k] = html_escape("");
        }
    }

    std::ostringstream result;
    size_t length = template_str.size();
    size_t i = 0;

    while (i < length) {
        if (template_str[i] == '{') {
            if (i + 1 < length && template_str[i + 1] == '{') {
                result << '{';
                i += 2;
                continue;
            }
            size_t start = i + 1;
            size_t end = template_str.find('}', start);
            if (end == std::string::npos) {
                throw std::runtime_error("Unclosed placeholder in template");
            }
            std::string key = template_str.substr(start, end - start);
            auto it = safe_data.find(key);
            if (it == safe_data.end()) {
                throw std::runtime_error("KeyError: " + key);
            }
            result << it->second;
            i = end + 1;
        } else if (template_str[i] == '}') {
            if (i + 1 < length && template_str[i + 1] == '}') {
                result << '}';
                i += 2;
                continue;
            }
            result << template_str[i];
            i += 1;
        } else {
            result << template_str[i];
            i += 1;
        }
    }

    return result.str();
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

void assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::exception&) {
        return;
    }
    fail("Expected an exception but none was raised");
}

int main() {
    // Test 1: Safe profile
    {
        Dict safe_profile = {
            {"profile_template", std::string("<div><h1>{title}</h1><p>{description}</p></div>")},
            {"page_data", Dict{
                {"title", std::string("Safe Profile")},
                {"description", std::string("Welcome to my profile.")}
            }}
        };
        std::string result = render_profile_page(safe_profile);
        expect_equal(result, "<div><h1>Safe Profile</h1><p>Welcome to my profile.</p></div>", "Test 1: Safe profile");
    }

    // Test 2: Bio with markup (XSS prevention)
    {
        Dict bio_with_markup = {
            {"profile_template", std::string("<div>{bio}</div>")},
            {"page_data", Dict{
                {"bio", std::string("<script>alert(\"X\")</script>")}
            }}
        };
        std::string result = render_profile_page(bio_with_markup);
        expect_equal(result, "<div>&lt;script&gt;alert(&quot;X&quot;)&lt;/script&gt;</div>", "Test 2: Bio with markup");
    }

    // Test 3: Mixed special characters
    {
        Dict mixed = {
            {"profile_template", std::string("<span>{x}</span>")},
            {"page_data", Dict{
                {"x", std::string("A & B < C")}
            }}
        };
        std::string result = render_profile_page(mixed);
        expect_equal(result, "<span>A &amp; B &lt; C</span>", "Test 3: Mixed special characters");
    }

    // Test 4: Numeric value (represented as string in C++ Dict)
    {
        Dict numeric = {
            {"profile_template", std::string("<p>{n}</p>")},
            {"page_data", Dict{
                {"n", std::string("123")}
            }}
        };
        std::string result = render_profile_page(numeric);
        expect_equal(result, "<p>123</p>", "Test 4: Numeric value");
    }

    // Test 5: Missing key in page_data
    {
        assert_raises([]() {
            Dict missing_key = {
                {"profile_template", std::string("<p>{missing}</p>")},
                {"page_data", Dict{}}
            };
            render_profile_page(missing_key);
        });
    }

    // Test 6: Invalid profile_template type
    {
        assert_raises([]() {
            Dict invalid_template = {
                {"profile_template", Dict{}},
                {"page_data", Dict{}}
            };
            render_profile_page(invalid_template);
        });
    }

    // Test 7: Missing required keys (page_data)
    {
        assert_raises([]() {
            Dict missing_page_data = {
                {"profile_template", std::string("<p>{x}</p>")}
            };
            render_profile_page(missing_page_data);
        });
    }

    // Test 8: Missing required keys (profile_template)
    {
        assert_raises([]() {
            Dict missing_template = {
                {"page_data", Dict{}}
            };
            render_profile_page(missing_template);
        });
    }

    std::cout << "All tests passed!" << std::endl;
    return 0;
}