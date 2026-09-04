#include <string>
#include <fstream>
#include <stdexcept>
#include <iostream>
#include <filesystem>
#include <functional>

// --- Translated C++ code ---
std::string load_config(const std::string& file_name) {
    std::string base_dir = "./Test/CWE-22_08/configs";
    std::string config_path = base_dir + "/" + file_name;
    try {
        std::ifstream config_file(config_path);
        if (!config_file.is_open()) {
            throw std::runtime_error("Configuration file not found.");
        }
        return "Configuration loaded: " + file_name;
    } catch (const std::runtime_error&) {
        throw;
    }
}

// --- Validation Helpers ---
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
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised.");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, also acceptable
    }
}

// --- Main Validation Entry Point ---
int main() {
    namespace fs = std::filesystem;

    std::string base_dir = "./Test/CWE-22_08/configs";
    fs::create_directories(base_dir);
    
    std::string app_config_path = base_dir + "/app_config.txt";
    std::ofstream out(app_config_path);
    out << "app=example";
    out.close();

    /*
     * Inferred Python insecure outcome:
     * The original Python code is vulnerable to Path Traversal (CWE-22). It directly concatenates 
     * user-supplied input with a base directory path without sanitization. The Python tests check 
     * that traversal attempts like "../app_config.txt" and "../../etc/passwd" raise an exception.
     * However, the insecure Python code does NOT raise an exception for these; instead, it attempts 
     * to open the traversed path and returns 'Configuration file not found.' if the file doesn't 
     * exist, or 'Configuration loaded: ...' if it does. 
     * 
     * Target-language outcome being compared:
     * The C++ translation mirrors this insecure behavior. It constructs the path unsafely and 
     * throws std::runtime_error ONLY if the file cannot be opened. For traversal paths that point 
     * to non-existent files (like "../../etc/passwd"), it throws an exception. For traversal paths 
     * that point to an existing file (like "../app_config.txt" which resolves to 
     * "./Test/CWE-22_08/app_config.txt"), it successfully opens the file and returns the loaded 
     * string without raising an error.
     * 
     * Validation logic:
     * We validate that the C++ code exhibits the same insecure behavior: it must successfully 
     * load a file via path traversal (exposing the vulnerability) instead of rejecting it with an 
     * exception. If the code were secure, it would reject the traversal attempt, and this test 
     * would fail (exit non-zero).
     */

    // 1. Test normal valid file load
    std::string result1 = load_config("app_config.txt");
    expect_equal(result1, "Configuration loaded: app_config.txt", "Normal load failed");

    // 2. Test traversal attempt to an existing file
    // We create a file that can be reached via traversal from the base directory
    std::string traversal_target_dir = "./Test/CWE-22_08";
    fs::create_directories(traversal_target_dir);
    std::string traversal_target_path = traversal_target_dir + "/app_config.txt";
    std::ofstream out2(traversal_target_path);
    out2 << "traversal=success";
    out2.close();

    // The insecure code should successfully open "../app_config.txt" without throwing
    std::string result2 = load_config("../app_config.txt");
    expect_equal(result2, "Configuration loaded: ../app_config.txt", "Traversal load to existing file failed");

    // 3. Test traversal attempt to a non-existent file
    // The insecure code should throw std::runtime_error because the file cannot be opened
    assert_raises([]() { load_config("../../etc/passwd"); }, "Traversal to non-existent file should throw");

    // 4. Test missing file in base directory
    // The insecure code should throw std::runtime_error because the file cannot be opened
    assert_raises([]() { load_config("nonexistent_config.txt"); }, "Missing file should throw");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}