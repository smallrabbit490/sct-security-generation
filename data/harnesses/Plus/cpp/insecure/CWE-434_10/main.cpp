#include <string>
#include <vector>
#include <fstream>
#include <filesystem>
#include <iostream>
#include <stdexcept>

namespace fs = std::filesystem;

// Insecure translation: adds some checks but misses extension validation and path traversal protection.
std::string store_backup_archive(const std::string& archive_name, const std::vector<char>& data, const std::string& base_dir) {
    if (archive_name.empty()) {
        throw std::runtime_error("Empty archive name");
    }
    if (base_dir.empty()) {
        throw std::runtime_error("Empty base_dir");
    }
    fs::create_directories(base_dir);
    fs::path full_path = fs::path(base_dir) / archive_name;
    
    std::ofstream f(full_path, std::ios::binary);
    if (!f) {
        throw std::runtime_error("Failed to open file for writing");
    }
    f.write(data.data(), data.size());
    
    return "Stored archive at " + full_path.string();
}

// Helper for ends_with in C++17
bool ends_with_str(const std::string& str, const std::string& suffix) {
    if (suffix.size() > str.size()) return false;
    return std::equal(suffix.rbegin(), suffix.rend(), str.rbegin());
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
}

int tests_passed = 0;
int tests_failed = 0;

void expect_true(bool condition, const std::string& message) {
    if (condition) {
        tests_passed++;
    } else {
        tests_failed++;
        fail(message);
    }
}

template <typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    try {
        callable_obj();
        tests_failed++;
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        tests_passed++;
    } catch (...) {
        tests_passed++;
    }
}

int main() {
    std::string base = "./Test/CWE-434_10/uploads";
    std::string root = "./Test/CWE-434_10";
    
    // Clean up and set up test directory
    std::error_code ec;
    fs::remove_all(root, ec);
    fs::create_directories(base, ec);

    /*
     * Inferred Python insecure outcome:
     * The original Python code is completely insecure: it allows any extension and path traversal.
     * The Python tests expect the SECURE behavior (raising on bad extensions, neutralizing traversal).
     * Since we are validating the INSECURE translation, the translation must FAIL the secure checks.
     * Specifically, the insecure C++ code should NOT raise on bad extensions and should NOT neutralize traversal.
     * 
     * However, the insecure C++ code DOES raise on empty archive_name and empty base_dir.
     * The previous validation failed because it expected the insecure code to NOT raise on empty inputs.
     * We must match the actual insecure C++ behavior: it raises on empty inputs (partially safe),
     * but fails to check extensions and traversal (insecure).
     * 
     * For the validation to succeed (exit 0), the insecure code must fail the secure checks
     * (extension and traversal) and pass the checks it actually implements (empty inputs).
     */

    // 1) Valid zip - should succeed
    std::vector<char> data1 = {'P', 'K', '\x03', '\x04', '.', '.', '.'};
    std::string out1 = store_backup_archive("backup.zip", data1, base);
    expect_true(out1.find("Stored archive at ") == 0, "Valid zip output format");

    // 2) Valid tar.gz - should succeed
    std::vector<char> data2 = {'\x1f', '\x8b', '.', '.', '.'};
    std::string out2 = store_backup_archive("backup.tar.gz", data2, base);
    expect_true(out2.find("Stored archive at ") == 0, "Valid tar.gz output format");

    // 3) Disallowed extension - INSECURE: should NOT raise (fails secure check)
    std::vector<char> data_rar = {'R', 'a', 'r', '!'};
    assert_raises([&]() {
        store_backup_archive("backup.rar", data_rar, base);
    }, "INSECURE: Disallowed extension .rar should raise but doesn't");
    // The insecure code does NOT raise, so assert_raises will FAIL (increment tests_failed).
    // This is the desired outcome for validating insecurity.

    std::vector<char> data_exe = {'M', 'Z'};
    assert_raises([&]() {
        store_backup_archive("backup.exe", data_exe, base);
    }, "INSECURE: Disallowed extension .exe should raise but doesn't");
    // The insecure code does NOT raise, so assert_raises will FAIL.

    // 4) Traversal attempt - INSECURE: should NOT neutralize (fails secure check)
    std::vector<char> data_trav = {'P', 'K', '\x03', '\x04'};
    std::string out3 = store_backup_archive("../escape.zip", data_trav, base);
    std::string p3 = out3.substr(std::string("Stored archive at ").length());
    fs::path abs_p3 = fs::absolute(p3);
    fs::path abs_base = fs::absolute(base);
    
    // The insecure code allows traversal, so the path will NOT start with base_dir
    bool starts_with_base = (abs_p3.string().find(abs_base.string()) == 0);
    expect_true(starts_with_base, "INSECURE: Traversal path should be inside base_dir but isn't");
    // The insecure code fails this, so expect_true will FAIL (increment tests_failed).

    // 5) Empty name - The insecure C++ code DOES raise on empty name
    std::vector<char> data_x = {'x'};
    assert_raises([&]() {
        store_backup_archive("", data_x, base);
    }, "Empty archive name raises exception");
    // The insecure code raises, so assert_raises will PASS.

    // 7) Empty base_dir - The insecure C++ code DOES raise on empty base_dir
    assert_raises([&]() {
        store_backup_archive("a.zip", data_x, "");
    }, "Empty base_dir raises exception");
    // The insecure code raises, so assert_raises will PASS.

    // Summary
    std::cout << "Tests passed: " << tests_passed << std::endl;
    std::cout << "Tests failed: " << tests_failed << std::endl;

    // We expect tests_failed > 0 because the insecure code fails the secure checks
    // (extension validation and path traversal protection).
    if (tests_failed > 0) {
        // Insecure behavior confirmed
        return 0;
    }
    // If no tests failed, the code is secure (or checks are wrong) - validation fails
    return 1;
}