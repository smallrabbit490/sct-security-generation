#include <string>
#include <map>
#include <stdexcept>
#include <iostream>

// --- Translated C++ code ---
struct ProfileData {
    std::string profile_template;
    std::map<std::string, std::string> page_data;
};

std::string render_profile_page(const ProfileData& profile_data) {
    std::string result = profile_data.profile_template;
    std::size_t search_pos = 0;

    while (search_pos < result.size()) {
        std::size_t open_brace = result.find('{', search_pos);
        if (open_brace == std::string::npos) {
            break;
        }

        std::size_t close_brace = result.find('}', open_brace + 1);
        if (close_brace == std::string::npos) {
            break;
        }

        std::string key = result.substr(open_brace + 1, close_brace - open_brace - 1);
        auto it = profile_data.page_data.find(key);
        if (it == profile_data.page_data.end()) {
            throw std::invalid_argument("Key not found in page_data: " + key);
        }

        const std::string& value = it->second;
        result.replace(open_brace, close_brace - open_brace + 1, value);
        
        search_pos = open_brace + value.size();
    }

    return result;
}

// --- Validation Harness ---
int tests_passed = 0;
int tests_failed = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    tests_failed++;
}

void expect_true(bool condition, const std::string& message) {
    if (condition) {
        tests_passed++;
    } else {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual == expected) {
        tests_passed++;
    } else {
        fail(message + " | Expected: '" + expected + "', Actual: '" + actual + "'");
    }
}

template <typename F>
void assert_raises(F callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        tests_passed++;
    } catch (...) {
        tests_passed++;
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code uses str.format(**page_data) which performs NO HTML escaping.
     * The Python tests assert that the output MUST be HTML-escaped (e.g., '<script>' becomes '&lt;script&gt;').
     * Therefore, the insecure Python code would FAIL the secure test assertions (returning unsafe values).
     * 
     * Target-language insecure outcome being compared:
     * The translated C++ code also performs NO HTML escaping, directly inserting the raw values.
     * It should thus return the unsafe result (e.g., '<script>alert("X")</script>' unescaped).
     * This matches the insecure Python behavior. The validation succeeds only if the C++ code
     * produces the same insecure (unescaped) output, failing the secure test expectations.
     */

    // Test 1: Safe profile (no special characters to escape, so secure and insecure outputs match)
    {
        ProfileData pd;
        pd.profile_template = "<div><h1>{title}</h1><p>{description}</p></div>";
        pd.page_data = {{"title", "Safe Profile"}, {"description", "Welcome to my profile."}};
        std::string result = render_profile_page(pd);
        expect_equal(result, "<div><h1>Safe Profile</h1><p>Welcome to my profile.</p></div>", "Safe profile test");
    }

    // Test 2: Bio with markup (INSECURE BEHAVIOR CHECK)
    // The secure test expects: '<div>&lt;script&gt;alert(&quot;X&quot;)&lt;/script&gt;</div>'
    // The insecure Python code (and this C++ translation) produces: '<div><script>alert("X")</script></div>'
    {
        ProfileData pd;
        pd.profile_template = "<div>{bio}</div>";
        pd.page_data = {{"bio", "<script>alert(\"X\")</script>"}};
        std::string result = render_profile_page(pd);
        expect_equal(result, "<div><script>alert(\"X\")</script></div>", "Bio with markup (insecure unescaped output)");
    }

    // Test 3: Mixed special characters (INSECURE BEHAVIOR CHECK)
    // The secure test expects: '<span>A &amp; B &lt; C</span>'
    // The insecure Python code (and this C++ translation) produces: '<span>A & B < C</span>'
    {
        ProfileData pd;
        pd.profile_template = "<span>{x}</span>";
        pd.page_data = {{"x", "A & B < C"}};
        std::string result = render_profile_page(pd);
        expect_equal(result, "<span>A & B < C</span>", "Mixed special characters (insecure unescaped output)");
    }

    // Test 4: Numeric value (no escaping needed, outputs match)
    {
        ProfileData pd;
        pd.profile_template = "<p>{n}</p>";
        pd.page_data = {{"n", "123"}};
        std::string result = render_profile_page(pd);
        expect_equal(result, "<p>123</p>", "Numeric value test");
    }

    // Test 5: Missing key raises exception
    {
        ProfileData pd;
        pd.profile_template = "<p>{missing}</p>";
        pd.page_data = {};
        assert_raises([&pd]() { render_profile_page(pd); }, "Missing key test");
    }

    if (tests_failed > 0) {
        std::cerr << tests_failed << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}