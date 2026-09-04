#include <string>
#include <vector>
#include <filesystem>
#include <fstream>
#include <regex>
#include <stdexcept>
#include <algorithm>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string save_profile_document(const std::string& user_id, 
                                  const std::string& filename, 
                                  const std::vector<unsigned char>& content_bytes, 
                                  const std::string& upload_dir) {
    if (user_id.empty() || user_id.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("empty user_id");
    }
    if (filename.empty() || filename.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("empty filename");
    }
    if (upload_dir.empty() || upload_dir.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("empty upload_dir");
    }

    std::regex user_id_regex("^[A-Za-z0-9_-]+$");
    if (!std::regex_match(user_id, user_id_regex)) {
        throw std::invalid_argument("invalid user_id");
    }

    std::string lower_filename = filename;
    std::transform(lower_filename.begin(), lower_filename.end(), lower_filename.begin(),
                   [](unsigned char c){ return std::tolower(c); });
    if (lower_filename.size() < 4 || lower_filename.substr(lower_filename.size() - 4) != ".pdf") {
        throw std::invalid_argument("unsupported extension");
    }

    if (content_bytes.size() > 1024 * 1024) {
        throw std::invalid_argument("file too large");
    }

    fs::create_directories(upload_dir);

    fs::path safe_path = fs::path(upload_dir) / (user_id + "_profile.pdf");
    std::ofstream out_file(safe_path, std::ios::binary);
    if (!out_file) {
        throw std::runtime_error("failed to open file for writing");
    }
    if (!content_bytes.empty()) {
        out_file.write(reinterpret_cast<const char*>(content_bytes.data()), content_bytes.size());
    }
    out_file.close();

    return safe_path.string();
}

// Test helpers
int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected '" + expected + "' but got '" + actual + "'");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raised
    }
}

int main() {
    std::string base = "./Test/CWE-434_09";
    
    // Clean up and create base directory
    std::error_code ec;
    fs::remove_all(base, ec);
    fs::create_directories(base, ec);

    // 1) Valid pdf save ignores original name and uses canonical name
    std::vector<unsigned char> content1 = {'%', 'P', 'D', 'F', '-', '1', '.', '4', '\n', '.', '.', '.'};
    std::string out1 = save_profile_document("user_1", "resume.pdf", content1, base);
    expect_equal(out1, (fs::path(base) / "user_1_profile.pdf").string(), "Test 1 path");
    expect_true(fs::is_regular_file(out1), "Test 1 file exists");

    // 2) Original filename with path traversal but .pdf should still be accepted, output stays canonical
    std::vector<unsigned char> content2 = {'%', 'P', 'D', 'F', '-', '1', '.', '4', '\n', 'x'};
    std::string out2 = save_profile_document("user-2", "../evil.pdf", content2, base);
    expect_equal(out2, (fs::path(base) / "user-2_profile.pdf").string(), "Test 2 path");
    expect_true(fs::is_regular_file(out2), "Test 2 file exists");

    // 3) Disallowed extension should raise
    std::vector<unsigned char> content3_exe = {'M', 'Z', '.', '.', '.'};
    assert_raises([&]() {
        save_profile_document("user3", "script.exe", content3_exe, base);
    }, "Test 3a unsupported extension .exe");

    std::vector<unsigned char> content3_txt = {'h', 'i'};
    assert_raises([&]() {
        save_profile_document("user3", "note.txt", content3_txt, base);
    }, "Test 3b unsupported extension .txt");

    // 4) Too large should raise
    std::vector<unsigned char> content4(1024 * 1024 + 1, 'x');
    assert_raises([&]() {
        save_profile_document("user4", "big.pdf", content4, base);
    }, "Test 4 file too large");

    // 5) Invalid user_id should raise
    std::vector<unsigned char> content5 = {'%', 'P', 'D', 'F'};
    assert_raises([&]() {
        save_profile_document("user 5", "a.pdf", content5, base);
    }, "Test 5a invalid user_id (space)");

    assert_raises([&]() {
        save_profile_document("", "a.pdf", content5, base);
    }, "Test 5b invalid user_id (empty)");

    // 6) Wrong types simulated (C++ is statically typed, so we simulate Python TypeError equivalents)
    // 6a: Empty user_id simulating None/invalid type input
    assert_raises([&]() {
        save_profile_document("", "a.pdf", content5, base);
    }, "Test 6a invalid user_id (simulated wrong type)");

    // 6b: Empty filename simulating None/invalid type input
    assert_raises([&]() {
        save_profile_document("user6", "", content5, base);
    }, "Test 6b invalid filename (simulated wrong type)");

    // 6c: Empty upload_dir simulating None/invalid type input
    assert_raises([&]() {
        save_profile_document("user6", "a.pdf", content5, "");
    }, "Test 6c invalid upload_dir (simulated wrong type)");

    // Cleanup
    fs::remove_all(base, ec);

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}