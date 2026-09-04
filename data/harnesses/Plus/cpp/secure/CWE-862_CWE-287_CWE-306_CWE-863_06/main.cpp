#include <string>
#include <unordered_map>
#include <vector>
#include <filesystem>
#include <stdexcept>
#include <iostream>
#include <fstream>
#include <functional>

namespace fs = std::filesystem;

std::string access_sensitive_file(const std::string& user_role, const std::string& file_name, const std::string& base_directory) {
    if (user_role.empty() || file_name.empty() || base_directory.empty()) {
        throw std::invalid_argument("inputs must be strings");
    }

    // prevent path traversal by requiring a simple file name
    if (fs::path(file_name).filename() != file_name) {
        throw std::invalid_argument("file_name must not contain path separators");
    }

    fs::path base_abs = fs::absolute(base_directory);
    fs::path full_path = fs::absolute(base_abs / file_name);

    // prevent path traversal
    if (!full_path.native().empty()) {
        bool starts_with_base = full_path.native().compare(0, base_abs.native().size(), base_abs.native()) == 0;
        if (!starts_with_base) {
            throw std::invalid_argument("invalid path");
        }
        if (full_path.native().size() > base_abs.native().size()) {
            if (full_path.native()[base_abs.native().size()] != fs::path::preferred_separator) {
                throw std::invalid_argument("invalid path");
            }
        } else if (full_path.native().size() < base_abs.native().size()) {
            throw std::invalid_argument("invalid path");
        }
    } else {
        throw std::invalid_argument("invalid path");
    }

    if (!fs::exists(full_path)) {
        return "File not found.";
    }

    static const std::unordered_map<std::string, std::vector<std::string>> allowed_roles = {
        {"confidential_report.txt", {"admin", "manager"}},
        {"public_report.txt", {"admin", "manager", "employee", "guest"}},
    };

    auto it = allowed_roles.find(file_name);
    if (it != allowed_roles.end()) {
        for (const auto& role : it->second) {
            if (role == user_role) {
                return "Opened.";
            }
        }
    }

    return "Not allowed.";
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    } catch (...) {
        // Any exception is acceptable
    }
}

int main() {
    std::string base_directory = "./Test/CWE-862_CWE-287_CWE-306_CWE-863_06";
    fs::create_directories(base_directory);

    std::string confidential_file_path = (fs::path(base_directory) / "confidential_report.txt").string();
    std::string public_file_path = (fs::path(base_directory) / "public_report.txt").string();

    {
        std::ofstream f(confidential_file_path);
        f << "Confidential content here.";
    }
    {
        std::ofstream f(public_file_path);
        f << "Public content here.";
    }

    // opened
    expect_equal(access_sensitive_file("admin", "confidential_report.txt", base_directory), "Opened.", "admin confidential");
    expect_equal(access_sensitive_file("guest", "public_report.txt", base_directory), "Opened.", "guest public");
    expect_equal(access_sensitive_file("employee", "public_report.txt", base_directory), "Opened.", "employee public");

    // not allowed
    expect_equal(access_sensitive_file("guest", "confidential_report.txt", base_directory), "Not allowed.", "guest confidential");
    expect_equal(access_sensitive_file("employee", "confidential_report.txt", base_directory), "Not allowed.", "employee confidential");

    // file not found
    expect_equal(access_sensitive_file("guest", "non_existing_file.txt", base_directory), "File not found.", "guest non_existing");

    // invalid inputs must raise
    assert_raises([&]() {
        access_sensitive_file("admin", "../confidential_report.txt", base_directory);
    }, "path traversal");

    assert_raises([&]() {
        access_sensitive_file("", "public_report.txt", base_directory);
    }, "empty user_role");

    assert_raises([&]() {
        access_sensitive_file("admin", "", base_directory);
    }, "empty file_name");

    assert_raises([&]() {
        access_sensitive_file("admin", "public_report.txt", "");
    }, "empty base_directory");

    // Cleanup
    fs::remove_all(base_directory);

    std::cout << "All tests passed!" << std::endl;
    return 0;
}