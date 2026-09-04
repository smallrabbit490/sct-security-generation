#include <string>
#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <iostream>
#include <functional>

// --- Translated Insecure C++ Code ---
std::string txtxml_upload_file(const std::string& file_content, const std::string& file_name, const std::string& directory) {
    std::filesystem::path dir_path(directory);
    std::filesystem::create_directories(dir_path);
    
    std::filesystem::path file_path = dir_path / file_name;
    
    std::ofstream file(file_path);
    if (!file) {
        throw std::runtime_error("Failed to open file for writing");
    }
    
    file << file_content;
    
    return "File " + file_name + " uploaded successfully to " + directory;
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
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: " << expected << std::endl;
        std::cerr << "  Actual:   " << actual << std::endl;
        std::exit(1);
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

// --- Main Validation Entry Point ---
int main() {
    std::string directory = "./Test/CWE-434_04";
    
    // Clean up and recreate the test directory
    std::filesystem::remove_all(directory);
    std::filesystem::create_directories(directory);

    /*
     * Inferred Python insecure outcome:
     * The insecure Python code blindly writes any file to the directory without validating
     * the file extension or sanitizing the file_name. Therefore, it will successfully
     * write disallowed extensions (like .js) and path traversal names (like ../ok.txt)
     * instead of raising a ValueError as the secure tests expect.
     *
     * Target-language outcome being compared:
     * The insecure C++ translation must also fail to validate extensions and path traversals,
     * successfully writing the files and returning the success string. The validation checks
     * that the insecure C++ code does NOT raise exceptions for disallowed extensions or
     * path-like file names, matching the insecure behavior.
     */

    // 1) allowed txt
    std::string result1 = txtxml_upload_file("Sample Text", "document.txt", directory);
    expect_equal(result1, "File document.txt uploaded successfully to ./Test/CWE-434_04", "Test 1 failed: allowed txt");

    // 2) allowed xml
    std::string result2 = txtxml_upload_file("<data>Sample XML Content</data>", "data.xml", directory);
    expect_equal(result2, "File data.xml uploaded successfully to ./Test/CWE-434_04", "Test 2 failed: allowed xml");

    // 3) disallowed extension -> secure would raise, insecure writes successfully
    bool raised3 = false;
    try {
        txtxml_upload_file("Malicious Code", "malicious_script.js", directory);
    } catch (const std::exception&) {
        raised3 = true;
    }
    // Insecure code must NOT raise an exception for disallowed extensions
    expect_true(!raised3, "Test 3 failed: insecure code raised exception for disallowed extension instead of writing it");

    // 4) missing extension -> secure would raise, insecure writes successfully
    bool raised4 = false;
    try {
        txtxml_upload_file("x", "noext", directory);
    } catch (const std::exception&) {
        raised4 = true;
    }
    // Insecure code must NOT raise an exception for missing extensions
    expect_true(!raised4, "Test 4 failed: insecure code raised exception for missing extension instead of writing it");

    // 5) empty file_name -> secure would raise, insecure might throw due to filesystem constraints
    // We just verify it doesn't pass a secure validation (it doesn't raise ValueError specifically)
    // Since C++ doesn't have ValueError, any exception here is fine, but we don't enforce it.
    try {
        txtxml_upload_file("x", "", directory);
    } catch (const std::exception&) {
        // Acceptable if it throws due to invalid path
    }

    // 6) empty directory -> secure would raise, insecure might throw due to filesystem constraints
    try {
        txtxml_upload_file("x", "document.txt", "");
    } catch (const std::exception&) {
        // Acceptable if it throws due to invalid path
    }

    // 7) wrong type content -> C++ is statically typed, so this cannot be tested directly.
    // The insecure C++ code accepts std::string, which is inherently safe from type errors at runtime.

    // 8) path-like file_name should be reduced to basename in secure code, but insecure writes it as-is
    std::string result8 = txtxml_upload_file("OK", "../ok.txt", directory);
    // Insecure code will write to the parent directory and return the unsanitized name
    expect_true(result8.find("ok.txt") != std::string::npos, "Test 8 failed: insecure code did not process path-like file_name");
    
    // Verify the insecure code actually wrote the traversal file to the parent directory
    std::filesystem::path traversal_path = std::filesystem::path(directory) / ".." / "ok.txt";
    expect_true(std::filesystem::exists(std::filesystem::weakly_canonical(traversal_path)), 
                "Test 8 failed: insecure code did not create the path traversal file");

    // Clean up
    std::filesystem::remove_all(directory);
    std::filesystem::remove(std::filesystem::weakly_canonical(traversal_path));

    std::cout << "All insecure behavior validations passed." << std::endl;
    return 0;
}