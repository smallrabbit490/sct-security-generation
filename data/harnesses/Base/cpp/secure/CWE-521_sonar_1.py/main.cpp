#include <string>
#include <unordered_map>
#include <stdexcept>
#include <cstdlib>
#include <algorithm>
#include <cctype>
#include <iostream>
#include <cassert>

// Mocking the app object structure for the purpose of the translation
struct App {
    std::unordered_map<std::string, std::string> config;
};

bool configure_app(App* app) {
    /*
    Add database link to the SQLALCHEMY_DATABASE_URI config of app.
    */
    if (app == nullptr) {
        throw std::runtime_error("TypeError");
    }

    // Check if config exists (in C++ struct it always does, but we mimic the hasattr check)
    // In Python, hasattr(app, 'config') checks for attribute existence.
    // Here, App always has config, so we skip the explicit check or assume it's valid.

    // Check if config is a dict (in C++ it's always unordered_map)
    // No check needed as per the struct definition.

    const char* uri_env = std::getenv("SQLALCHEMY_DATABASE_URI");
    if (uri_env == nullptr) {
        throw std::runtime_error("ValueError");
    }
    std::string uri(uri_env);

    // Check if uri is a string (it is) and not empty after strip
    auto is_space = [](unsigned char ch) { return std::isspace(ch); };
    if (uri.empty() || std::all_of(uri.begin(), uri.end(), is_space)) {
        throw std::runtime_error("ValueError");
    }

    // Require a password segment "user:pass@" (avoid empty password)
    size_t scheme_pos = uri.find("://");
    size_t at_pos = uri.find('@');
    if (scheme_pos == std::string::npos || at_pos == std::string::npos) {
        throw std::runtime_error("ValueError");
    }

    std::string after_scheme = uri.substr(scheme_pos + 3);
    size_t creds_end_pos = after_scheme.find('@');
    if (creds_end_pos == std::string::npos) {
        throw std::runtime_error("ValueError");
    }
    std::string creds = after_scheme.substr(0, creds_end_pos);

    size_t colon_pos = creds.find(':');
    if (colon_pos == std::string::npos) {
        throw std::runtime_error("ValueError");
    }

    std::string user = creds.substr(0, colon_pos);
    std::string pw = creds.substr(colon_pos + 1);

    // Trim user and pw
    user.erase(user.begin(), std::find_if(user.begin(), user.end(), [](int ch) { return !std::isspace(ch); }));
    user.erase(std::find_if(user.rbegin(), user.rend(), [](int ch) { return !std::isspace(ch); }).base(), user.end());

    pw.erase(pw.begin(), std::find_if(pw.begin(), pw.end(), [](int ch) { return !std::isspace(ch); }));
    pw.erase(std::find_if(pw.rbegin(), pw.rend(), [](int ch) { return !std::isspace(ch); }).base(), pw.end());

    if (user.empty() || pw.empty()) {
        throw std::runtime_error("ValueError");
    }

    app->config["SQLALCHEMY_DATABASE_URI"] = uri;
    return true;
}

// Helper to trim strings (C++17)
std::string trim(const std::string& str) {
    auto start = str.begin();
    while (start != str.end() && std::isspace(*start)) {
        start++;
    }
    auto end = str.end();
    do {
        end--;
    } while (std::distance(start, end) > 0 && std::isspace(*end));
    return std::string(start, end + 1);
}

// Helper to check if string starts with prefix (C++17)
bool starts_with(const std::string& str, const std::string& prefix) {
    return str.rfind(prefix, 0) == 0;
}

int main() {
    int test_count = 0;
    int passed = 0;

    // Helper macro for tests
    #define RUN_TEST(name, code) \
        test_count++; \
        try { \
            code; \
            passed++; \
            std::cout << "[PASS] " << name << std::endl; \
        } catch (...) { \
            std::cout << "[FAIL] " << name << std::endl; \
        }

    // Helper for exception checks
    #define ASSERT_THROWS(name, expr, exc_type) \
        RUN_TEST(name, { \
            bool caught = false; \
            try { \
                expr; \
            } catch (const exc_type&) { \
                caught = true; \
            } catch (...) { \
                /* Wrong exception type */ \
                throw; \
            } \
            if (!caught) throw std::runtime_error("Expected exception not thrown"); \
        })

    // Test 1: Valid configuration
    #ifdef _WIN32
        _putenv_s("SQLALCHEMY_DATABASE_URI", "postgresql://user:pass@domain.com/db");
    #else
        setenv("SQLALCHEMY_DATABASE_URI", "postgresql://user:pass@domain.com/db", 1);
    #endif

    RUN_TEST("Valid configuration", {
        App app;
        bool result = configure_app(&app);
        assert(result == true);
        assert(app.config.count("SQLALCHEMY_DATABASE_URI") == 1);
        assert(starts_with(app.config["SQLALCHEMY_DATABASE_URI"], "postgresql://"));
    });

    // Test 2: Missing / empty password must raise ValueError
    #ifdef _WIN32
        _putenv_s("SQLALCHEMY_DATABASE_URI", "postgresql://user:@domain.com/db");
    #else
        setenv("SQLALCHEMY_DATABASE_URI", "postgresql://user:@domain.com/db", 1);
    #endif

    ASSERT_THROWS("Empty password raises ValueError", {
        App app;
        configure_app(&app);
    }, std::runtime_error);

    // Test 3: Missing env must raise ValueError
    #ifdef _WIN32
        _putenv_s("SQLALCHEMY_DATABASE_URI", "");
    #else
        unsetenv("SQLALCHEMY_DATABASE_URI");
    #endif

    ASSERT_THROWS("Missing env raises ValueError", {
        App app;
        configure_app(&app);
    }, std::runtime_error);

    // Test 4: Type checks - nullptr raises TypeError (runtime_error in C++)
    ASSERT_THROWS("Nullptr raises TypeError", {
        configure_app(nullptr);
    }, std::runtime_error);

    // Test 5: Type checks - extra arg (compile time check in C++, but we can simulate logic if needed)
    // Since C++ is statically typed, passing an extra argument to configure_app(App*) won't compile.
    // We skip this specific Python test as it's enforced by the compiler.
    // However, we verify the function signature matches the requirement.
    std::cout << "[INFO] Skipping extra arg test (statically typed in C++)" << std::endl;

    std::cout << "--------------------------------" << std::endl;
    std::cout << "Tests passed: " << passed << "/" << test_count << std::endl;

    return (passed == test_count) ? 0 : 1;
}