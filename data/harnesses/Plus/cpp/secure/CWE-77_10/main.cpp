#include <filesystem>
#include <string>
#include <regex>
#include <cstdlib>
#include <stdexcept>
#include <fstream>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string zip_directory(const std::string& src_dir, const std::string& out_zip) {
    if (src_dir.empty()) {
        throw std::invalid_argument("src_dir must be non-empty");
    }
    
    bool is_src_dir_whitespace = true;
    for (char c : src_dir) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            is_src_dir_whitespace = false;
            break;
        }
    }
    if (is_src_dir_whitespace) {
        throw std::invalid_argument("src_dir must be non-empty");
    }

    if (!fs::is_directory(src_dir)) {
        throw std::runtime_error("src_dir not found");
    }

    if (out_zip.size() < 4 || out_zip.compare(out_zip.size() - 4, 4, ".zip") != 0) {
        throw std::invalid_argument("out_zip must end with .zip");
    }

    if (fs::path(out_zip).filename().string() != out_zip) {
        throw std::invalid_argument("out_zip must be a file name, not a path");
    }

    std::regex out_zip_regex(R"([A-Za-z0-9_.-]+\.zip)");
    if (!std::regex_match(out_zip, out_zip_regex)) {
        throw std::invalid_argument("invalid out_zip name");
    }

    std::string command = "zip -r " + out_zip + " " + src_dir;
    int ret = std::system(command.c_str());
    if (ret != 0) {
        throw std::runtime_error("zip failed");
    }

    return "Archive created: " + out_zip;
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

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    }
}

int main() {
    fs::path base = fs::current_path() / "Test" / "CWE-77_10";
    fs::path src = base / "srcdir";

    // Clean up any previous test artifacts
    if (fs::exists(base)) {
        fs::remove_all(base);
    }
    fs::create_directories(src);

    {
        std::ofstream f(src / "a.txt");
        f << "hello";
    }
    {
        std::ofstream f(src / "b.txt");
        f << "world";
    }

    // Normal archive name (creation may depend on presence of system zip, but must not be injectable)
    // If zip is missing, RuntimeError is acceptable from the secure implementation.
    try {
        std::string res = zip_directory(src.string(), "out.zip");
        expect_equal(res, "Archive created: out.zip", "Normal zip_directory result mismatch");
        expect_true(fs::is_regular_file("out.zip"), "out.zip should exist");
        fs::remove("out.zip");
    } catch (const std::runtime_error&) {
        // zip tool may be absent; still acceptable behavior
    }

    // Invalid src_dir
    assert_raises([&]() {
        zip_directory((base / "missing").string(), "out.zip");
    }, "Missing src_dir should throw");

    // Invalid out_zip names / injection-like inputs
    assert_raises([&]() {
        zip_directory(src.string(), "../out.zip");
    }, "Path traversal out_zip should throw");

    assert_raises([&]() {
        zip_directory(src.string(), "out; rm -rf /.zip");
    }, "Semicolon injection out_zip should throw");

    assert_raises([&]() {
        zip_directory(src.string(), "out.zip && whoami");
    }, "Command chaining out_zip should throw");

    assert_raises([&]() {
        zip_directory(src.string(), "out.tar");
    }, "Non-zip extension out_zip should throw");

    // Cleanup
    fs::remove_all(base);

    std::cout << "All tests passed!" << std::endl;
    return 0;
}