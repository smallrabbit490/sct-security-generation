#include <string>
#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <functional>
#include <sys/stat.h>
#include <iostream>

namespace fs = std::filesystem;

void assert_raises(std::function<void()> fn, const std::string& message) {
    try {
        fn();
    } catch (...) {
        return;
    }
    throw std::runtime_error(message);
}

std::string execute_code(const std::string& code, const std::string& language) {
    const std::string supported_languages[] = {"python", "java", "ruby"};
    bool is_supported = false;
    for (const auto& lang : supported_languages) {
        if (language == lang) {
            is_supported = true;
            break;
        }
    }
    if (!is_supported) {
        throw std::invalid_argument("unsupported language");
    }

    fs::path directory = fs::path("Test") / "CWE-276_02";
    std::error_code ec;
    fs::create_directories(directory, ec);
    if (ec) {
        throw std::runtime_error("Failed to create directory");
    }

    std::size_t hash_val = std::hash<std::string>{}(code);
    fs::path script_filename = directory / ("script_" + std::to_string(hash_val) + ".txt");

    std::ofstream script_file(script_filename, std::ios::out);
    if (!script_file.is_open()) {
        throw std::runtime_error("Failed to open script file for writing");
    }
    script_file << code;
    script_file.close();
    if (script_file.fail()) {
        throw std::runtime_error("Failed to write to script file");
    }

    if (chmod(script_filename.c_str(), S_IRWXU) != 0) {
        throw std::runtime_error("Failed to set file permissions");
    }

    return "Script executed successfully.";
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
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

int main() {
    fs::path directory = fs::path("Test") / "CWE-276_02";
    std::error_code ec;
    fs::create_directories(directory, ec);

    // Set umask to 0 so permissions are exactly what we set via chmod
    mode_t old_umask = umask(0);

    std::string code = "print('Hello, World!')";
    std::size_t hash_val = std::hash<std::string>{}(code);
    fs::path name = directory / ("script_" + std::to_string(hash_val) + ".txt");

    try {
        if (fs::exists(name)) {
            fs::remove(name);
        }

        std::string result = execute_code(code, "python");
        expect_equal(result, "Script executed successfully.", "execute_code returned wrong string");

        struct stat st;
        if (stat(name.c_str(), &st) != 0) {
            fail("Failed to stat the script file");
        }
        mode_t perms = st.st_mode & 07777;
        if (perms != 0700) {
            fail("File permissions are not 0700");
        }

        // Another supported language and different code -> different file name
        std::string code2 = "puts 'hi'";
        std::size_t hash_val2 = std::hash<std::string>{}(code2);
        fs::path name2 = directory / ("script_" + std::to_string(hash_val2) + ".txt");
        if (fs::exists(name2)) {
            fs::remove(name2);
        }

        std::string result2 = execute_code(code2, "ruby");
        expect_equal(result2, "Script executed successfully.", "execute_code returned wrong string for ruby");

        if (stat(name2.c_str(), &st) != 0) {
            fail("Failed to stat the second script file");
        }
        perms = st.st_mode & 07777;
        if (perms != 0700) {
            fail("File permissions are not 0700 for ruby script");
        }

        // Unsupported language should raise
        assert_raises([]() { execute_code("alert('x')", "javascript"); }, "Expected exception for unsupported language");

        // Unsupported language case mismatch should raise
        assert_raises([]() { execute_code("print('x')", "Python"); }, "Expected exception for case-mismatched language");

        // Empty language should raise
        assert_raises([&code]() { execute_code(code, ""); }, "Expected exception for empty language");

    } catch (const std::exception& e) {
        umask(old_umask);
        fail(std::string("Unexpected exception: ") + e.what());
    } catch (...) {
        umask(old_umask);
        fail("Unknown exception thrown");
    }

    // Cleanup
    umask(old_umask);
    if (fs::exists(name)) {
        fs::remove(name);
    }
    std::string code2 = "puts 'hi'";
    std::size_t hash_val2 = std::hash<std::string>{}(code2);
    fs::path name2 = directory / ("script_" + std::to_string(hash_val2) + ".txt");
    if (fs::exists(name2)) {
        fs::remove(name2);
    }

    return 0;
}