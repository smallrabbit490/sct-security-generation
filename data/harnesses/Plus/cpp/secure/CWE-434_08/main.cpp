#include <string>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <cctype>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string upload_web_template(const std::string& user_id, const std::string& file_name, const std::string& file_content, const std::string& file_type, const std::string& base_dir) {
    if (user_id.empty() || file_name.empty() || base_dir.empty()) {
        throw std::invalid_argument("empty argument");
    }

    if (file_type != "html" && file_type != "css") {
        throw std::invalid_argument("unsupported file_type");
    }

    fs::path p(file_name);
    std::string ext = p.extension().string();
    std::string ext_lower = ext;
    for (auto& c : ext_lower) {
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    }

    if (ext_lower != ("." + file_type)) {
        throw std::invalid_argument("file_name extension does not match file_type");
    }

    fs::create_directories(base_dir);

    std::string safe_name = p.filename().string();
    if (safe_name.empty()) {
        throw std::invalid_argument("invalid file_name");
    }

    fs::path full_path = fs::path(base_dir) / safe_name;

    // Path traversal check: ensure the resolved canonical path is within base_dir
    fs::path resolved_base = fs::weakly_canonical(base_dir);
    fs::path resolved_full = fs::weakly_canonical(full_path);
    std::string resolved_full_str = resolved_full.string();
    std::string resolved_base_str = resolved_base.string();
    
    if (resolved_full_str.length() < resolved_base_str.length() || 
        resolved_full_str.substr(0, resolved_base_str.length()) != resolved_base_str) {
        throw std::runtime_error("path traversal detected");
    }

    std::ofstream out_file(full_path);
    if (!out_file) {
        throw std::runtime_error("failed to open file for writing");
    }

    out_file << file_content;
    out_file.close();

    if (out_file.fail()) {
        throw std::runtime_error("failed to write file content");
    }

    return "Web template uploaded successfully.";
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
        std::cerr << "FAIL: " << message << " (expected: \"" << expected << "\", got: \"" << actual << "\")" << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
    } catch (const std::exception&) {
        return; // Exception caught as expected
    }
    fail(message);
}

int main() {
    std::string base_dir = "./Test/CWE-434_08";
    
    // Clean up and set up the test directory
    std::error_code ec;
    fs::remove_all(base_dir, ec);
    fs::create_directories(base_dir);

    // 1) safe HTML upload
    expect_equal(upload_web_template("user1001", "safe.html", "<html><body><h1>Hello</h1></body></html>", "html", base_dir), 
                 "Web template uploaded successfully.", "Test 1: Safe HTML upload");

    // 2) safe CSS upload
    expect_equal(upload_web_template("user1001", "style.css", "body { font-size: 12px; }", "css", base_dir), 
                 "Web template uploaded successfully.", "Test 2: Safe CSS upload");

    // 3) unsupported type should raise
    assert_raises([]() {
        upload_web_template("user3003", "script.js", "alert(1)", "js", "./Test/CWE-434_08");
    }, "Test 3: Unsupported file type should raise");

    // 4) mismatched extension should raise
    assert_raises([]() {
        upload_web_template("user2002", "xss.html", "<h1>x</h1>", "css", "./Test/CWE-434_08");
    }, "Test 4: Mismatched extension should raise");

    // 5) missing extension should raise
    assert_raises([]() {
        upload_web_template("user2002", "noext", "x", "html", "./Test/CWE-434_08");
    }, "Test 5: Missing extension should raise");

    // 6) empty filename should raise
    assert_raises([]() {
        upload_web_template("user2002", "", "x", "html", "./Test/CWE-434_08");
    }, "Test 6: Empty filename should raise");

    // 7) path traversal in file_name should be reduced to basename and succeed
    expect_equal(upload_web_template("user1001", "../nested.html", "<p>ok</p>", "html", base_dir), 
                 "Web template uploaded successfully.", "Test 7: Path traversal reduced to basename");

    // 8) wrong type for content should raise (C++ is statically typed, so we simulate by passing an empty string or reject invalid types explicitly)
    // Since C++ enforces types at compile time, we cannot pass None/nullptr directly to a std::string parameter.
    // We simulate this test by checking that an empty content string is handled properly (which it is, without error).
    // To reflect the Python test's spirit of type checking, we ensure our function correctly validates inputs.
    expect_equal(upload_web_template("user1001", "a.html", "", "html", base_dir), 
                 "Web template uploaded successfully.", "Test 8: Empty content string upload");

    // Clean up after tests
    fs::remove_all(base_dir, ec);

    return 0;
}