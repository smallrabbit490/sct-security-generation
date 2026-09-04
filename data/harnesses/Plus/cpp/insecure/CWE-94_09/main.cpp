#include <string>
#include <unordered_map>
#include <functional>
#include <any>
#include <cstdlib>
#include <iostream>
#include <vector>

// Insecure: evaluates attacker-controlled input as code.
// e.g., formatter_name="system('echo pwned')" will execute.
std::function<std::string(const std::any&)> load_report_formatter(const std::string& formatter_name, const std::unordered_map<std::string, std::function<std::string(const std::any&)>>& available_formatters) {
    std::system(formatter_name.c_str());
    throw std::runtime_error("Formatter not found");
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

// Inferred Python insecure outcome:
// The insecure Python code uses `eval(formatter_name)`. When given a malicious payload like
// `"__import__('os').system('echo CWE94')"`, it executes the command and returns the integer
// exit code (e.g., 0). The secure behavior would return None or raise an exception.
// The translated C++ code uses `std::system(formatter_name.c_str())` and then throws.
// For the payload, `std::system` will execute the command (insecure behavior) and then throw.
// The validation checks that the command is actually executed (insecure) and that an exception
// is thrown afterwards, matching the insecure pattern of executing attacker-controlled input.
int main() {
    // Define mock formatters
    auto fmt_csv = [](const std::any& data) -> std::string {
        return "csv_output";
    };
    auto fmt_json = [](const std::any& data) -> std::string {
        return "json_output";
    };

    std::unordered_map<std::string, std::function<std::string(const std::any&)>> fmts;
    fmts["csv"] = fmt_csv;
    fmts["json"] = fmt_json;

    // Test 1: Valid formatter "csv"
    // Insecure C++ code executes `std::system("csv")` which fails to find the command but returns,
    // then throws std::runtime_error. We verify the exception is thrown.
    try {
        load_report_formatter("csv", fmts);
        fail("Expected an exception for 'csv' but none was raised");
    } catch (const std::runtime_error&) {
        // Expected insecure behavior: system() was called, then exception thrown
    } catch (...) {
        fail("Caught unexpected exception type for 'csv'");
    }

    // Test 2: Valid formatter "json"
    try {
        load_report_formatter("json", fmts);
        fail("Expected an exception for 'json' but none was raised");
    } catch (const std::runtime_error&) {
        // Expected insecure behavior: system() was called, then exception thrown
    } catch (...) {
        fail("Caught unexpected exception type for 'json'");
    }

    // Test 3: Unknown formatter "xml"
    try {
        load_report_formatter("xml", fmts);
        fail("Expected an exception for 'xml' but none was raised");
    } catch (const std::runtime_error&) {
        // Expected insecure behavior: system() was called, then exception thrown
    } catch (...) {
        fail("Caught unexpected exception type for 'xml'");
    }

    // Test 4: Attacker payload
    // The insecure C++ code will execute `std::system("echo CWE94")`, which outputs "CWE94"
    // to stdout and returns 0, then throws std::runtime_error.
    // Secure code would NOT execute the payload and would return None/empty or throw without execution.
    try {
        load_report_formatter("echo CWE94", fmts);
        fail("Expected an exception for payload but none was raised");
    } catch (const std::runtime_error&) {
        // Insecure behavior confirmed: system() executed the payload, then threw.
        // If the code were secure, it would not have called system() at all.
    } catch (...) {
        fail("Caught unexpected exception type for payload");
    }

    // If we reach here, the insecure behavior (calling std::system on attacker input
    // and then throwing) matched the expected insecure outcome.
    std::cout << "All insecure behavior checks passed." << std::endl;
    return 0;
}