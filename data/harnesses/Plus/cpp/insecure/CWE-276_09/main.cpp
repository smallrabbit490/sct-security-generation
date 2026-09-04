#include <string>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

// --- Translated C++ code ---
std::string export_user_report(const std::string& user_id, const std::string& report_text) {
    fs::path base_dir = "Test/CWE-276_09/reports";
    fs::path user_dir = base_dir / user_id;
    
    fs::create_directories(user_dir);

    fs::path path = user_dir / "report.txt";
    std::ofstream f(path);
    if (!f) {
        throw std::runtime_error("Failed to open file");
    }
    f << report_text;

    // Insecure: overly permissive permissions
    std::error_code ec;
    fs::permissions(user_dir, fs::perms::all, fs::perm_options::replace, ec);
    fs::permissions(path, fs::perms::owner_read | fs::perms::owner_write |
                          fs::perms::group_read | fs::perms::group_write |
                          fs::perms::others_read | fs::perms::others_write,
                    fs::perm_options::replace, ec);

    return "Report exported.";
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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message);
    }
}

int main() {
    fs::path base = "Test/CWE-276_09/reports";
    std::error_code ec;
    if (fs::exists(base, ec)) {
        fs::remove_all(base, ec);
    }

    /*
     * Inferred Python insecure outcome:
     * The Python insecure code does not validate user_id for path separators or traversal sequences.
     * It will successfully process "bad/user" and "../evil" by creating directories and files 
     * outside the intended user directory, without raising a ValueError.
     * The Python tests assert that a secure version SHOULD raise ValueError for these inputs.
     * Since the insecure code does NOT raise, it fails the secure test.
     * 
     * Target-language outcome being compared:
     * The C++ insecure translation similarly lacks validation for path separators or traversal.
     * It should NOT throw an exception for "bad/user" or "../evil".
     * If the C++ code does not throw, it matches the insecure behavior (success for validation).
     * If the C++ code throws an exception, it means the vulnerability was fixed (fail for validation).
     */

    // Test 1: valid user report
    std::string res1 = export_user_report("user123", "hello");
    expect_equal(res1, "Report exported.", "Valid user report return value");
    fs::path path1 = base / "user123" / "report.txt";
    expect_true(fs::exists(path1), "Valid user report file exists");

    // Test 2: another valid user_id
    std::string res2 = export_user_report("u_1-2", "x");
    expect_equal(res2, "Report exported.", "Second valid user report return value");
    fs::path path2 = base / "u_1-2" / "report.txt";
    expect_true(fs::exists(path2), "Second valid user report file exists");

    // Test 3: invalid user_id (path separator) - Insecure code should NOT raise
    {
        bool raised = false;
        try {
            export_user_report("bad/user", "x");
        } catch (const std::exception&) {
            raised = true;
        } catch (...) {
            raised = true;
        }
        if (raised) {
            fail("Insecure: Should NOT raise exception for path separator user_id");
        }
    }

    // Test 4: invalid user_id (traversal-like) - Insecure code should NOT raise
    {
        bool raised = false;
        try {
            export_user_report("../evil", "x");
        } catch (const std::exception&) {
            raised = true;
        } catch (...) {
            raised = true;
        }
        if (raised) {
            fail("Insecure: Should NOT raise exception for traversal-like user_id");
        }
    }

    // Cleanup
    if (fs::exists(base, ec)) {
        fs::remove_all(base, ec);
    }

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}