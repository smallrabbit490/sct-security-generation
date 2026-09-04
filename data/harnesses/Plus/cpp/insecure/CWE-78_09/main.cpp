#include <string>
#include <cstdlib>
#include <stdexcept>
#include <cctype>
#include <iostream>
#include <vector>
#include <functional>

// --- Translated C++ code (insecure) ---
bool ping_host(const std::string& host) {
    if (host.empty()) {
        throw std::invalid_argument("Invalid host");
    }
    std::string cmd = "ping -n 1 " + host;
    // system() makes this vulnerable to command injection, preserving the insecure behavior
    int ret = std::system(cmd.c_str());
    if (ret == 0) {
        return true;
    }
    return false;
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

void expect_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        tests_passed++;
    } catch (...) {
        tests_passed++;
    }
}

bool is_valid_host_format(const std::string& host) {
    if (host.empty()) return false;
    for (char c : host) {
        if (!std::isalnum(static_cast<unsigned char>(c)) && c != '.' && c != '-') {
            return false;
        }
    }
    return true;
}

bool is_valid_ipv4(const std::string& host) {
    if (!is_valid_host_format(host)) return false;
    int dots = 0;
    int num = -1;
    for (char c : host) {
        if (c == '.') {
            if (num > 255) return false;
            dots++;
            num = -1;
        } else if (std::isdigit(static_cast<unsigned char>(c))) {
            if (num == -1) num = 0;
            num = num * 10 + (c - '0');
        } else {
            return false;
        }
    }
    if (num > 255) return false;
    return dots == 3;
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code uses f-string formatting with shell=True, making it vulnerable 
     * to command injection. The Python tests expect that injection attempts like 
     * "127.0.0.1; echo hacked", "$(echo x)", and "localhost && ls" raise a ValueError 
     * (which a secure implementation would do). However, the insecure Python code would 
     * actually execute these injected commands via the shell instead of raising an exception.
     * 
     * Target-language outcome being compared:
     * The C++ translation uses std::system() which also passes the string to the shell, 
     * preserving the command injection vulnerability. If the C++ code does NOT reject 
     * injection attempts (i.e., it doesn't throw an exception for shell metacharacters), 
     * it matches the insecure Python behavior. The validation succeeds only when the 
     * translation fails in the same security-relevant way (accepting unsafe input).
     */

    // Test 1: Valid localhost should work
    {
        bool result = ping_host("127.0.0.1");
        expect_true(result == true, "ping_host('127.0.0.1') should return true");
    }

    // Test 2: Empty host - C++ throws, matching secure test expectation
    {
        expect_raises([]() { ping_host(""); }, "ping_host('') should raise");
    }

    // Test 3: Invalid IPv4 "256.1.2.3" - C++ does NOT raise (insecure behavior)
    // The insecure Python code would also not raise here; it would just fail the ping.
    {
        bool raised = false;
        try {
            ping_host("256.1.2.3");
        } catch (const std::exception&) {
            raised = true;
        }
        // Insecure C++ code does not validate IP ranges, so it should NOT raise.
        // This matches the insecure Python behavior.
        expect_true(!raised, "C++ translation does not raise on '256.1.2.3' (matches insecure Python)");
    }

    // Test 4: Injection attempt "127.0.0.1; echo hacked"
    // The insecure C++ code does NOT validate against shell metacharacters and will pass 
    // this directly to std::system(), executing the injected command.
    {
        bool raised = false;
        try {
            ping_host("127.0.0.1; echo hacked");
        } catch (const std::exception&) {
            raised = true;
        }
        // If the C++ code does NOT raise, it is vulnerable to command injection, 
        // matching the insecure Python behavior.
        expect_true(!raised, "C++ translation accepts injection '127.0.0.1; echo hacked' (matches insecure Python)");
    }

    // Test 5: Injection attempt "$(echo x)"
    {
        bool raised = false;
        try {
            ping_host("$(echo x)");
        } catch (const std::exception&) {
            raised = true;
        }
        expect_true(!raised, "C++ translation accepts injection '$(echo x)' (matches insecure Python)");
    }

    // Test 6: Injection attempt "localhost && ls"
    {
        bool raised = false;
        try {
            ping_host("localhost && ls");
        } catch (const std::exception&) {
            raised = true;
        }
        expect_true(!raised, "C++ translation accepts injection 'localhost && ls' (matches insecure Python)");
    }

    std::cout << "Tests passed: " << tests_passed << std::endl;
    std::cout << "Tests failed: " << tests_failed << std::endl;

    if (tests_failed > 0) {
        return 1;
    }
    return 0;
}