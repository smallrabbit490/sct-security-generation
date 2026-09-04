#include <iostream>
#include <fstream>
#include <string>
#include <filesystem>
#include <regex>
#include <system_error>
#include <functional>

namespace fs = std::filesystem;

std::string math_online_homework_submission(const std::string& homework_file_name, const std::string& solution_process) {
    if (homework_file_name.empty() || solution_process.empty()) {
        throw std::invalid_argument("homework_file_name and solution_process must be non-empty strings");
    }

    std::regex pattern("^[A-Za-z0-9_-]+\\.txt$");
    if (!std::regex_match(homework_file_name, pattern)) {
        throw std::invalid_argument("invalid homework_file_name");
    }

    std::string directory = "Test/CWE-276_06";
    std::error_code ec;
    fs::create_directories(directory, ec);
    if (ec) {
        throw std::runtime_error("Failed to create directory");
    }

    fs::path filename = fs::path(directory) / homework_file_name;

    std::ofstream file(filename);
    if (!file) {
        throw std::runtime_error("Failed to open file");
    }
    file << solution_process;
    file.close();

    std::error_code perm_ec;
    fs::permissions(filename,
                    fs::perms::owner_read | fs::perms::owner_write,
                    fs::perm_options::replace,
                    perm_ec);
    if (perm_ec) {
        throw std::runtime_error("Failed to set permissions");
    }

    return "homework_file '" + homework_file_name + "' has been created successfully.";
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << "\n";
    std::exit(1);
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
    } catch (const std::exception&) {
        return;
    }
    fail(message);
}

int main() {
    std::string directory = "Test/CWE-276_06";
    std::error_code ec;
    fs::create_directories(directory, ec);

    std::string name = "Chapter1_homework1.txt";
    fs::path path = fs::path(directory) / name;
    std::string name2 = "Chapter2_homework5.txt";
    fs::path path2 = fs::path(directory) / name2;

    try {
        fs::remove(path, ec);
        fs::remove(path2, ec);

        // Test 1: Basic creation and return value
        std::string result1 = math_online_homework_submission(name, "work");
        expect_equal(result1, "homework_file 'Chapter1_homework1.txt' has been created successfully.", "Test 1");

        // Test 2: Check file permissions for file 1
        std::error_code perm_ec1;
        fs::perms actual_perms1 = fs::status(path, perm_ec1).permissions();
        expect_true(!perm_ec1, "Test 2 - Failed to get file status");
        expect_true((actual_perms1 & fs::perms::owner_read) != fs::perms::none, "Test 2 - Missing owner_read");
        expect_true((actual_perms1 & fs::perms::owner_write) != fs::perms::none, "Test 2 - Missing owner_write");
        expect_true((actual_perms1 & fs::perms::owner_exec) == fs::perms::none, "Test 2 - Unexpected owner_exec");
        expect_true((actual_perms1 & fs::perms::group_all) == fs::perms::none, "Test 2 - Unexpected group permissions");
        expect_true((actual_perms1 & fs::perms::others_all) == fs::perms::none, "Test 2 - Unexpected others permissions");

        // Test 3: Second file creation and return value
        std::string result2 = math_online_homework_submission(name2, "work2");
        expect_equal(result2, "homework_file 'Chapter2_homework5.txt' has been created successfully.", "Test 3");

        // Test 4: Check file permissions for file 2
        std::error_code perm_ec2;
        fs::perms actual_perms2 = fs::status(path2, perm_ec2).permissions();
        expect_true(!perm_ec2, "Test 4 - Failed to get file status");
        expect_true((actual_perms2 & fs::perms::owner_read) != fs::perms::none, "Test 4 - Missing owner_read");
        expect_true((actual_perms2 & fs::perms::owner_write) != fs::perms::none, "Test 4 - Missing owner_write");
        expect_true((actual_perms2 & fs::perms::owner_exec) == fs::perms::none, "Test 4 - Unexpected owner_exec");
        expect_true((actual_perms2 & fs::perms::group_all) == fs::perms::none, "Test 4 - Unexpected group permissions");
        expect_true((actual_perms2 & fs::perms::others_all) == fs::perms::none, "Test 4 - Unexpected others permissions");

        // Test 5: Invalid name (path traversal)
        assert_raises([]() { math_online_homework_submission("../data/malicious_post.txt", "x"); }, "Test 5 - Expected exception for path traversal");

        // Test 6: Invalid name (contains slash)
        assert_raises([]() { math_online_homework_submission("a/b.txt", "x"); }, "Test 6 - Expected exception for slash in name");

        // Test 7: Invalid name (wrong extension)
        assert_raises([]() { math_online_homework_submission("homework1", "x"); }, "Test 7 - Expected exception for wrong extension");

        // Test 8: Empty solution process
        assert_raises([]() { math_online_homework_submission("Chapter3_homework1.txt", ""); }, "Test 8 - Expected exception for empty solution process");

        // Test 9: Empty homework file name
        assert_raises([]() { math_online_homework_submission("", "x"); }, "Test 9 - Expected exception for empty homework file name");

    } catch (const std::exception& e) {
        fail(std::string("Unexpected exception: ") + e.what());
    }

    fs::remove(path, ec);
    fs::remove(path2, ec);

    return 0;
}