#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <map>
#include <cassert>

// Translated Code
std::map<std::string, std::map<std::string, std::string>> get_DATABASES() {
    const char* env_pw = std::getenv("DJANGO_DB_PASSWORD");
    if (env_pw == nullptr) {
        throw std::runtime_error("Environment variable DJANGO_DB_PASSWORD not set");
    }

    std::string pw(env_pw);
    bool is_empty = true;
    for (char c : pw) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            is_empty = false;
            break;
        }
    }

    if (is_empty) {
        throw std::runtime_error("Database password cannot be empty");
    }

    std::map<std::string, std::map<std::string, std::string>> databases;
    std::map<std::string, std::string> config;

    config["ENGINE"] = "django.db.backends.postgresql";
    config["NAME"] = "quickdb";
    config["USER"] = "sonarsource";
    config["PASSWORD"] = pw;
    config["HOST"] = "localhost";
    config["PORT"] = "5432";

    databases["postgresql_db"] = config;

    return databases;
}

// Test Harness
int main() {
    try {
        // Test 1: Valid password
        // Note: In C++, we cannot strictly test "extra arg rejected" (TypeError) 
        // because get_DATABASES is a function, not a callable object with operator().
        // We also cannot unset environment variables portably in standard C++ 
        // (unsetenv is POSIX), so we simulate the missing env check by setting it to empty 
        // or relying on the fact that if it wasn't set at program start, it would fail.
        // However, to ensure the tests run deterministically, we set it here.
        
        #ifdef _WIN32
            _putenv_s("DJANGO_DB_PASSWORD", "p");
        #else
            setenv("DJANGO_DB_PASSWORD", "p", 1);
        #endif

        auto cfg = get_DATABASES();
        assert(cfg.count("postgresql_db") != 0);
        assert(cfg["postgresql_db"]["PASSWORD"] == "p");
        assert(cfg["postgresql_db"]["ENGINE"] == "django.db.backends.postgresql");

        // Test 2: Empty password must raise
        #ifdef _WIN32
            _putenv_s("DJANGO_DB_PASSWORD", "");
        #else
            setenv("DJANGO_DB_PASSWORD", "", 1);
        #endif
        
        bool raised = false;
        try {
            get_DATABASES();
        } catch (const std::runtime_error&) {
            raised = true;
        }
        assert(raised);

        // Test 3: Missing env must raise
        // Since we can't reliably unset env vars in pure standard C++, 
        // we check if the function throws when the var is not set.
        // If the var is still set from the previous step, we skip this specific check 
        // or acknowledge the limitation. However, the Python test pops it.
        // We will attempt to set it to empty (which is handled) or rely on the logic.
        // To strictly follow the "missing" logic, we would need unsetenv.
        // Given the constraints, we verify the logic handles nullptr if it were to occur.
        // Since we can't force nullptr via standard C++ after setting it, we assume the 
        // implementation is correct based on the code review.
        
        // If we are on a system supporting unsetenv, we can try:
        #if defined(__unix__) || (defined(__APPLE__) && defined(__MACH__))
            unsetenv("DJANGO_DB_PASSWORD");
            raised = false;
            try {
                get_DATABASES();
            } catch (const std::runtime_error&) {
                raised = true;
            }
            assert(raised);
        #endif

        std::cout << "All tests passed." << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Test failed: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "Test failed with unknown exception." << std::endl;
        return 1;
    }
}