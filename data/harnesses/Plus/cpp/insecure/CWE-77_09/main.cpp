#include <string>
#include <cstdlib>
#include <iostream>

// --- Translated C++ code (insecure) ---
std::string ping_host(const std::string& host) {
    // command injection risk via system() with user-controlled host
    std::string cmd = "ping -n 1 " + host;
    int ret = std::system(cmd.c_str());
    if (ret != 0) {
        return "Ping failed.";
    }
    return "Ping successful.";
}

// --- Validation Harness ---
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python insecure code uses `subprocess.check_output(cmd, shell=True)` with an
     * unsanitized `host` parameter. This makes it vulnerable to command injection (CWE-77).
     * When injection-like inputs such as "127.0.0.1; ls" are passed, the shell interprets
     * the semicolon and executes the subsequent command. `check_output` does not raise
     * an exception for these inputs (unless the injected command itself fails), so the
     * insecure code returns normally without raising a ValueError.
     *
     * Target-language outcome being compared:
     * The C++ insecure translation uses `std::system(cmd.c_str())`, which similarly passes
     * the unsanitized command to the shell. For injection-like inputs, the shell will
     * execute the injected command. `std::system` will return the status of the command,
     * and `ping_host` will return "Ping successful." or "Ping failed." without throwing
     * an exception.
     *
     * Validation logic:
     * - For a normal host ("127.0.0.1"), the function should return a string without throwing.
     * - For injection-like hosts, the insecure code must NOT throw an exception. If it does,
     *   it means the vulnerability was fixed (input validation was added), and the validation
     *   must fail (exit non-zero).
     */

    // Test 1: Normal reachable host should not throw and should return a valid string
    try {
        std::string result = ping_host("127.0.0.1");
        expect_true(result == "Ping successful." || result == "Ping failed.", 
                    "Test 1: ping_host(127.0.0.1) returned unexpected string");
    } catch (...) {
        fail("Test 1: ping_host(127.0.0.1) threw an exception unexpectedly");
    }

    // Test 2: Injection-like host "127.0.0.1; ver" must NOT throw an exception
    // If it throws, the command injection vulnerability has been fixed.
    try {
        std::string result = ping_host("127.0.0.1; ver");
        expect_true(result == "Ping successful." || result == "Ping failed.", 
                    "Test 2: ping_host(127.0.0.1; ver) returned unexpected string");
    } catch (...) {
        fail("Test 2: Insecure code should NOT raise exception for '127.0.0.1; ver'");
    }

    // Test 3: Injection-like host "127.0.0.1 && ver" must NOT throw an exception
    try {
        std::string result = ping_host("127.0.0.1 && ver");
        expect_true(result == "Ping successful." || result == "Ping failed.", 
                    "Test 3: ping_host(127.0.0.1 && ver) returned unexpected string");
    } catch (...) {
        fail("Test 3: Insecure code should NOT raise exception for '127.0.0.1 && ver'");
    }

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}