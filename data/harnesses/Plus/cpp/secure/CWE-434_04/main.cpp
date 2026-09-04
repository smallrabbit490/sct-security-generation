#include <string>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <set>
#include <algorithm>
#include <iostream>
#include <functional>
#include <cctype>

namespace fs = std::filesystem;

std::string txtxml_upload_file(const std::string& file_content, const std::string& file_name, const std::string& directory) {
    if (file_name.empty()) {
        throw std::invalid_argument("empty file_name");
    }

    bool dir_is_whitespace = true;
    for (char c : directory) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            dir_is_whitespace = false;
            break;
        }
    }
    if (dir_is_whitespace) {
        throw std::invalid_argument("empty directory");
    }

    size_t dot_pos = file_name.rfind('.');
    if (dot_pos == std::string::npos || dot_pos == file_name.length() - 1) {
        throw std::invalid_argument("file_name must have an extension");
    }

    std::string ext = file_name.substr(dot_pos + 1);
    std::transform(ext.begin(), ext.end(), ext.begin(),
                   [](unsigned char c){ return std::tolower(c); });

    static const std::set<std::string> allowed = {"txt", "xml"};
    if (allowed.find(ext) == allowed.end()) {
        throw std::invalid_argument("unsupported extension");
    }

    fs::create_directories(directory);

    fs::path base_path = fs::path(file_name).filename();
    if (base_path.empty()) {
        throw std::invalid_argument("invalid file_name");
    }
    std::string base = base_path.string();

    fs::path full_path = fs::path(directory) / base_path;

    std::ofstream out_file(full_path);
    if (!out_file) {
        throw std::runtime_error("Failed to open file for writing");
    }
    out_file << file_content;
    out_file.close();
    if (out_file.fail()) {
        throw std::runtime_error("Failed to write file content");
    }

    return "File " + base + " uploaded successfully to " + directory;
}

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
        fail(message + " - Expected: '" + expected + "', Actual: '" + actual + "'");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    } catch (...) {
        // Any exception caught is acceptable
    }
}

int main() {
    std::string directory = "./Test/CWE-434_04";
    
    // Clean up and set up directory
    std::error_code ec;
    if (fs::exists(directory, ec)) {
        fs::remove_all(directory, ec);
    }
    fs::create_directories(directory, ec);

    // 1) allowed txt
    expect_equal(
        txtxml_upload_file("Sample Text", "document.txt", directory),
        "File document.txt uploaded successfully to ./Test/CWE-434_04",
        "Test 1: allowed txt"
    );

    // 2) allowed xml
    expect_equal(
        txtxml_upload_file("<data>Sample XML Content</data>", "data.xml", directory),
        "File data.xml uploaded successfully to ./Test/CWE-434_04",
        "Test 2: allowed xml"
    );

    // 3) disallowed extension -> raise (insecure would write)
    assert_raises([]() {
        txtxml_upload_file("Malicious Code", "malicious_script.js", "./Test/CWE-434_04");
    }, "Test 3: disallowed extension");

    // 4) missing extension -> raise
    assert_raises([]() {
        txtxml_upload_file("x", "noext", "./Test/CWE-434_04");
    }, "Test 4: missing extension");

    // 5) empty file_name -> raise
    assert_raises([]() {
        txtxml_upload_file("x", "", "./Test/CWE-434_04");
    }, "Test 5: empty file_name");

    // 6) empty directory -> raise
    assert_raises([]() {
        txtxml_upload_file("x", "document.txt", "");
    }, "Test 6: empty directory");

    // 7) wrong type content -> raise
    // In C++, strong typing prevents passing None/non-strings to std::string parameters.
    // We simulate this by ensuring the function correctly handles empty/whitespace strings 
    // and rejects invalid arguments securely.
    assert_raises([]() {
        txtxml_upload_file("x", "document.txt", "   ");
    }, "Test 7: whitespace directory");

    // 8) path-like file_name should be reduced to basename and succeed
    expect_equal(
        txtxml_upload_file("OK", "../ok.txt", directory),
        "File ok.txt uploaded successfully to ./Test/CWE-434_04",
        "Test 8: path-like file_name"
    );

    // Clean up after tests
    fs::remove_all(directory, ec);

    return 0;
}