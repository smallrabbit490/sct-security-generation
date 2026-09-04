#include <filesystem>
#include <string>
#include <stdexcept>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

// Translated set_theme function
std::string set_theme(const std::string& username, const std::string& theme_path) {
    const std::string themes_directory = "Test/CWE-22_03";
    fs::path base_abs = fs::absolute(themes_directory);

    fs::path requested;
    // theme_path may be given as "Test/CWE-22_03/<theme>" or just "<theme>"
    if (theme_path.rfind(themes_directory, 0) == 0) {
        requested = theme_path;
    } else {
        requested = fs::path(themes_directory) / theme_path;
    }

    fs::path full_path = fs::absolute(requested);

    // Security control: prevent path traversal
    if (full_path != base_abs && !fs::relative(full_path, base_abs).string().empty() && fs::relative(full_path, base_abs).string()[0] == '.') {
        throw std::invalid_argument("invalid theme path");
    }
    if (full_path.parent_path() != base_abs && full_path != base_abs) {
        throw std::invalid_argument("invalid theme path");
    }

    if (!fs::is_directory(full_path)) {
        throw std::runtime_error("theme not found");
    }

    return "Theme set successfully for " + username + ".";
}

// Test helpers
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
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    }
}

// Overload for type-checking tests (accepting any type)
template <typename U, typename V>
void assert_raises_type(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::invalid_argument&) {
        // Caught expected invalid_argument
    } catch (const std::runtime_error&) {
        // Caught expected runtime_error
    } catch (const std::exception&) {
        // Caught other standard exceptions
    }
}

int main() {
    const std::string base_dir = "Test/CWE-22_03";

    // Setup test directories
    fs::create_directories(fs::path(base_dir) / "dog_theme");
    fs::create_directories(fs::path(base_dir) / "cat_theme");

    // Valid theme tests
    expect_equal(
        set_theme("user123", "Test/CWE-22_03/dog_theme"),
        "Theme set successfully for user123.",
        "set_theme with valid dog_theme"
    );

    expect_equal(
        set_theme("user789", "Test/CWE-22_03/cat_theme"),
        "Theme set successfully for user789.",
        "set_theme with valid cat_theme"
    );

    // Path traversal tests
    assert_raises(
        std::function<void()>([]() { set_theme("user456", "../../malicious_theme"); }),
        "set_theme with path traversal ../../malicious_theme"
    );

    assert_raises(
        std::function<void()>([]() { set_theme("user789", "themes/../../confidential/private"); }),
        "set_theme with path traversal themes/../../confidential/private"
    );

    // Missing theme directory test
    assert_raises(
        std::function<void()>([]() { set_theme("user000", "Test/CWE-22_03/missing_theme"); }),
        "set_theme with missing theme directory"
    );

    // Type checks (C++ enforces types at compile time, so passing non-strings is impossible.
    // We verify that the function correctly handles its string inputs and throws appropriately for bad paths).
    // To mirror the Python test's spirit of rejecting bad inputs, we ensure invalid paths raise exceptions.
    assert_raises(
        std::function<void()>([]() { set_theme("user", ""); }),
        "set_theme with empty theme path"
    );

    // Cleanup test directories
    fs::remove_all("Test");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}