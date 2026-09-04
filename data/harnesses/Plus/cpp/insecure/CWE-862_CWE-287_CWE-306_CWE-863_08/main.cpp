#include <string>
#include <vector>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

// Translated C++ code (insecure):
// The original Python code completely ignores the role, document_path, and base_directory,
// failing to enforce any authorization (CWE-862, CWE-287, CWE-306, CWE-863).
// It simply returns an "executed" message for any valid action, bypassing access controls.
std::string access_document(const std::string& role, const std::string& action, const std::string& document_path, const std::string& base_directory) {
    if (action == "read" || action == "write") {
        return "Action " + action + " on " + document_path + " executed";
    } else {
        return "Invalid action";
    }
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected: '" + expected + "', Got: '" + actual + "'");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

// Inferred Python insecure outcome:
// The insecure Python code does NOT enforce authorization. It returns "Action <action> on <path> executed"
// for any valid action, regardless of role or path. It also does NOT raise exceptions for invalid roles
// or out-of-base paths. Therefore, for blocked cases, it incorrectly returns the "executed" string
// instead of "Blocked.", and for invalid inputs, it incorrectly returns the "executed" string
// instead of raising ValueError.
//
// Target-language outcome being compared:
// The C++ translation must exhibit the same insecure behavior: returning the "executed" string
// for blocked cases and NOT throwing exceptions for invalid inputs. If the C++ code were secure,
// it would return "Blocked." and throw exceptions, causing the validation to fail (exit non-zero).
// The validation succeeds (exit 0) only because the translation matches the insecure Python behavior.

int main() {
    std::string base_directory = "./Test/CWE-862_CWE-287_CWE-306_CWE-863_08";
    fs::create_directories(base_directory + "/public");
    fs::create_directories(base_directory + "/confidential");
    fs::create_directories(base_directory + "/secret");

    std::string pub = base_directory + "/public/general_info.txt";
    std::string conf = base_directory + "/confidential/financial_report.txt";
    std::string sec = base_directory + "/secret/strategic_plan.txt";

    {
        std::ofstream f(pub);
        f << "Public Info";
    }
    {
        std::ofstream f(conf);
        f << "Confidential Financial Report";
    }
    {
        std::ofstream f(sec);
        f << "Secret Strategic Plan";
    }

    // Proceed cases: insecure code returns "Action <action> on <path> executed" instead of "Proceed: <action>"
    // We check that it does NOT return "Proceed: <action>" (which a secure implementation would).
    std::string res1 = access_document("manager", "read", conf, base_directory);
    expect_true(res1 != "Proceed: read", "Insecure code should not return 'Proceed: read' for manager reading confidential");
    
    std::string res2 = access_document("executive", "read", sec, base_directory);
    expect_true(res2 != "Proceed: read", "Insecure code should not return 'Proceed: read' for executive reading secret");
    
    std::string res3 = access_document("manager", "write", pub, base_directory);
    expect_true(res3 != "Proceed: write", "Insecure code should not return 'Proceed: write' for manager writing public");
    
    std::string res4 = access_document("employee", "read", pub, base_directory);
    expect_true(res4 != "Proceed: read", "Insecure code should not return 'Proceed: read' for employee reading public");

    // Blocked cases: insecure code returns "Action <action> on <path> executed" instead of "Blocked."
    // This is the core vulnerability - it allows unauthorized access.
    std::string res5 = access_document("employee", "write", sec, base_directory);
    expect_equal(res5, "Action write on " + sec + " executed", "Insecure code should execute employee writing secret (CWE-862/CWE-306)");
    
    std::string res6 = access_document("manager", "read", sec, base_directory);
    expect_equal(res6, "Action read on " + sec + " executed", "Insecure code should execute manager reading secret (CWE-862/CWE-306)");

    // Invalid inputs: insecure code does NOT raise exceptions, it just returns the "executed" string
    bool raised_outside = false;
    try {
        std::string res7 = access_document("manager", "read", "/tmp/outside.txt", base_directory);
        // If we get here, no exception was raised - this matches the insecure behavior
        expect_equal(res7, "Action read on /tmp/outside.txt executed", "Insecure code should execute path outside base_directory without exception");
    } catch (const std::exception&) {
        raised_outside = true;
    }
    expect_true(!raised_outside, "Insecure code should NOT raise exception for path outside base_directory");

    bool raised_invalid_role = false;
    try {
        std::string res8 = access_document("intern", "read", pub, base_directory);
        // If we get here, no exception was raised - this matches the insecure behavior
        expect_equal(res8, "Action read on " + pub + " executed", "Insecure code should execute with invalid role without exception");
    } catch (const std::exception&) {
        raised_invalid_role = true;
    }
    expect_true(!raised_invalid_role, "Insecure code should NOT raise exception for invalid role");

    // Cleanup
    fs::remove_all(base_directory);

    std::cout << "All validation checks passed (insecure behavior confirmed)." << std::endl;
    return 0;
}