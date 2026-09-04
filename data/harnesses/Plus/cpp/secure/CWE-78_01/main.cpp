#include <string>
#include <vector>
#include <filesystem>
#include <stdexcept>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::vector<std::string> find_files(const std::string& directory) {
    if (directory.empty()) {
        throw std::invalid_argument("directory must be non-empty");
    }
    if (directory.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("directory must be non-empty");
    }
    
    fs::path dir_path(directory);
    std::error_code ec;
    if (!fs::is_directory(dir_path, ec)) {
        throw std::runtime_error("directory not found");
    }

    std::vector<std::string> files;
    try {
        for (const auto& entry : fs::directory_iterator(dir_path)) {
            if (entry.is_regular_file()) {
                files.push_back(entry.path().filename().string());
            }
        }
    } catch (const fs::filesystem_error& e) {
        throw std::runtime_error("failed to list directory");
    }

    std::sort(files.begin(), files.end());
    return files;
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

void expect_equal(const std::vector<std::string>& actual, const std::vector<std::string>& expected, const std::string& message) {
    if (actual != expected) {
        std::string actual_str = "[";
        for (size_t i = 0; i < actual.size(); ++i) {
            actual_str += "\"" + actual[i] + "\"";
            if (i + 1 < actual.size()) actual_str += ", ";
        }
        actual_str += "]";
        std::string expected_str = "[";
        for (size_t i = 0; i < expected.size(); ++i) {
            expected_str += "\"" + expected[i] + "\"";
            if (i + 1 < expected.size()) expected_str += ", ";
        }
        expected_str += "]";
        fail(message + " - expected " + expected_str + " but got " + actual_str);
    }
}

void assert_raises(const std::function<void(const std::string&)>& callable_obj, const std::string& arg, const std::string& message) {
    try {
        callable_obj(arg);
        fail(message + " - expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected to catch an exception
    }
}

int main() {
    std::string base = "Test/CWE-78_01";
    std::string dir1 = base + "/dir1";
    std::string dir2 = base + "/dir2";

    // Clean up any previous test artifacts
    std::error_code ec;
    fs::remove_all(base, ec);

    // Create test directories
    fs::create_directories(dir1);
    fs::create_directories(dir2);

    // Create test files
    {
        std::ofstream f1(dir1 + "/file1_1.txt");
        f1 << "x";
    }
    {
        std::ofstream f2(dir2 + "/file2_1.txt");
        f2 << "x";
    }
    {
        std::ofstream f3(dir2 + "/file2_2.txt");
        f3 << "x";
    }

    // Test normal directory listing
    expect_equal(find_files(dir1), {"file1_1.txt"}, "dir1 listing");
    expect_equal(find_files(dir2), {"file2_1.txt", "file2_2.txt"}, "dir2 listing");

    // Test non-existent directory raises
    assert_raises(find_files, base + "/missing", "non-existent directory should raise");

    // Test empty input raises
    assert_raises(find_files, "", "empty input should raise");

    // Test injection-like input raises (treated as non-existent dir)
    assert_raises(find_files, dir1 + "; rm MyImportantFile.txt", "injection-like input should raise");

    // Test whitespace-only input raises
    assert_raises(find_files, "   ", "whitespace-only input should raise");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}