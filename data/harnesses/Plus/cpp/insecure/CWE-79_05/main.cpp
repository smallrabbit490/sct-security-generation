#include <string>
#include <map>
#include <stdexcept>
#include <iostream>

// Translated C++ code (insecure: does not escape HTML characters)
std::map<std::string, std::string> create_profile(const std::string& user_id, const std::string& full_name, const std::string& bio) {
    // Unsafe: Directly using the user-submitted bio and user_id
    std::map<std::string, std::string> profile_data = {
        {"user_id", user_id},
        {"full_name", full_name},
        {"bio", bio}
    };
    return profile_data;
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

// Inferred Python insecure outcome:
// The Python insecure code does NOT escape HTML special characters. It directly returns the raw input strings.
// The secure tests expect HTML characters to be escaped (e.g., '<' becomes '&lt;'). 
// Therefore, the insecure Python code would FAIL the secure tests by returning the raw, unescaped strings.
// 
// Target-language outcome being compared:
// The C++ translation also does NOT escape HTML characters. It returns the raw input strings.
// We validate that the C++ translation matches the insecure behavior (returning unescaped strings).
// If the C++ code were secure (escaping HTML), it would pass the secure test expectations, 
// and this validation would exit non-zero because the vulnerability would be fixed.

int main() {
    // Test 1: No markup here!
    auto result1 = create_profile("user111", "Charlie Brown", "No markup here!");
    expect_equal(result1["user_id"], "user111", "Test 1 user_id");
    expect_equal(result1["full_name"], "Charlie Brown", "Test 1 full_name");
    expect_equal(result1["bio"], "No markup here!", "Test 1 bio");

    // Test 2: HTML in bio (insecure: returns raw, unescaped string)
    auto result2 = create_profile("user456", "Jane Smith", "<img src='malicious.jpg'>This is another bio.");
    expect_equal(result2["user_id"], "user456", "Test 2 user_id");
    expect_equal(result2["full_name"], "Jane Smith", "Test 2 full_name");
    // Insecure behavior: does NOT escape to &lt;img src=&#x27;malicious.jpg&#x27;&gt;
    expect_equal(result2["bio"], "<img src='malicious.jpg'>This is another bio.", "Test 2 bio (insecure unescaped)");

    // Test 3: HTML in user_id (insecure: returns raw, unescaped string)
    auto result3 = create_profile("<script>alert('x')</script>", "Alice Davis", "This is a normal bio.");
    // Insecure behavior: does NOT escape to &lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;
    expect_equal(result3["user_id"], "<script>alert('x')</script>", "Test 3 user_id (insecure unescaped)");
    expect_equal(result3["full_name"], "Alice Davis", "Test 3 full_name");
    expect_equal(result3["bio"], "This is a normal bio.", "Test 3 bio");

    // Test 4: Special characters in all fields (insecure: returns raw, unescaped strings)
    auto result4 = create_profile("u&v", "A<B", "He said \"ok\"");
    // Insecure behavior: does NOT escape to u&amp;v, A&lt;B, He said &quot;ok&quot;
    expect_equal(result4["user_id"], "u&v", "Test 4 user_id (insecure unescaped)");
    expect_equal(result4["full_name"], "A<B", "Test 4 full_name (insecure unescaped)");
    expect_equal(result4["bio"], "He said \"ok\"", "Test 4 bio (insecure unescaped)");

    // Test 5: TypeError checks (C++ std::string constructor prevents non-string types at compile time)
    // Passing `1` (int) or `nullptr` to `const std::string&` is either a compile error or throws std::bad_alloc/logic_error.
    // This matches the Python insecure behavior of raising an exception for invalid types.
    bool threw_exception = false;
    try {
        // Passing nullptr to const std::string& typically throws std::logic_error in C++
        auto result5 = create_profile(nullptr, "Name", "Bio");
        (void)result5;
    } catch (const std::exception&) {
        threw_exception = true;
    }
    expect_true(threw_exception, "Expected an exception for nullptr argument");

    // If all checks pass, the C++ code successfully exhibits the same insecure behavior as the Python code.
    return 0;
}