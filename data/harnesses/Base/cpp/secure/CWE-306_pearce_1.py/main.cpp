#include <iostream>
#include <string>
#include <stdexcept>
#include <unordered_map>
#include <functional>
#include <cassert>

// Simulating a session storage
std::unordered_map<std::string, std::string> session;

// Entry point function equivalent to Python's settings
std::string settings() {
    // Check if the user is authenticated
    // In Python: if session.get('username') is None:
    // In C++ simulation: if key missing or value is empty string (representing None)
    if (session.find("username") == session.end() || session["username"].empty()) {
        throw std::runtime_error("PermissionError");
    }
    // Return the confidential settings page content
    return "<html>Secret settings</html>";
}

// Helper to assert that a function throws a specific exception type
void assert_raises(std::function<void()> func, const std::string& expected_msg) {
    try {
        func();
        // If no exception was thrown, fail the test
        std::cerr << "Test Failed: Expected exception '" << expected_msg << "' but none was thrown." << std::endl;
        std::exit(1);
    } catch (const std::runtime_error& e) {
        if (std::string(e.what()) != expected_msg) {
            std::cerr << "Test Failed: Expected exception '" << expected_msg << "' but got '" << e.what() << "'" << std::endl;
            std::exit(1);
        }
    } catch (...) {
        std::cerr << "Test Failed: Expected exception '" << expected_msg << "' but got a different type." << std::endl;
        std::exit(1);
    }
}

int main() {
    // 1) Not logged in -> must raise
    session.clear();
    assert_raises([]() { settings(); }, "PermissionError");

    // 2) Logged in -> ok
    session.clear();
    session["username"] = "admin";
    {
        std::string out = settings();
        if (out.find("Secret settings") == std::string::npos) {
            std::cerr << "Test Failed: Expected 'Secret settings' in output." << std::endl;
            return 1;
        }
    }

    // 3) Explicit None -> raise
    // In C++ simulation, we represent None as an empty string for the username value
    session.clear();
    session["username"] = ""; 
    assert_raises([]() { settings(); }, "PermissionError");

    // 4) Extra arg rejected
    // C++ is statically typed, so passing an extra argument to settings() 
    // results in a compilation error. We simulate the logic check by 
    // verifying the function signature matches the expected usage.
    // Since settings() takes no arguments, this is implicitly satisfied by compilation.
    // We perform a runtime check to ensure the function object is callable with no args.
    std::function<std::string()> func = settings;
    (void)func; // Suppress unused warning

    // 5) Another logged-in user ok
    session.clear();
    session["username"] = "alice";
    {
        std::string out = settings();
        if (out.find("Secret settings") == std::string::npos) {
            std::cerr << "Test Failed: Expected 'Secret settings' in output for user alice." << std::endl;
            return 1;
        }
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}