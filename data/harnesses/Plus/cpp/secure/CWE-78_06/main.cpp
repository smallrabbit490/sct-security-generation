#include <filesystem>
#include <string>
#include <stdexcept>
#include <sstream>
#include <algorithm>
#include <fstream>
#include <functional>
#include <vector>
#include <cctype>
#include <iostream>
#include <cstdlib>

namespace fs = std::filesystem;

std::string list_files(const std::string& directory) {
    if (directory.empty()) {
        throw std::invalid_argument("directory must be non-empty");
    }
    if (std::all_of(directory.begin(), directory.end(), [](char c){ return std::isspace(static_cast<unsigned char>(c)); })) {
        throw std::invalid_argument("directory must be non-empty");
    }
    
    fs::path dir_path(directory);
    std::error_code ec;
    if (!fs::is_directory(dir_path, ec)) {
        throw std::runtime_error("directory not found");
    }

    std::ostringstream output;
    bool first = true;
    for (const auto& entry : fs::directory_iterator(dir_path, ec)) {
        if (ec) {
            throw std::runtime_error("ls failed");
        }
        if (!first) {
            output << "\n";
        }
        output << entry.path().filename().string();
        first = false;
    }

    if (ec) {
        throw std::runtime_error("ls failed");
    }

    return output.str();
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
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: \"" << expected << "\"" << std::endl;
        std::cerr << "  Actual:   \"" << actual << "\"" << std::endl;
        std::exit(1);
    }
}

void assert_raises(const std::function<void()>& func, const std::vector<std::string>& allowed_type_names) {
    try {
        func();
        fail("Expected exception but none was thrown");
    } catch (const std::exception& e) {
        std::string caught_type = typeid(e).name();
        bool found = false;
        for (const auto& name : allowed_type_names) {
            if (caught_type == name) {
                found = true;
                break;
            }
        }
        if (!found) {
            std::cerr << "FAIL: Exception type mismatch" << std::endl;
            std::cerr << "  Caught: " << caught_type << std::endl;
            std::cerr << "  Allowed:";
            for (const auto& name : allowed_type_names) {
                std::cerr << " " << name;
            }
            std::cerr << std::endl;
            std::exit(1);
        }
    }
}

int main() {
    // Setup test directory
    fs::path base_dir = fs::current_path() / "Test" / "CWE-78_06";
    fs::remove_all(base_dir);
    fs::create_directories(base_dir);

    std::vector<std::string> filenames = {"doc.txt", "image.png"};
    for (const auto& fn : filenames) {
        std::ofstream ofs(base_dir / fn);
        ofs << "dummy";
        ofs.close();
    }

    // Test listing files
    std::string result = list_files(base_dir.string());
    expect_true(result.find("doc.txt") != std::string::npos, "doc.txt should be in result");
    expect_true(result.find("image.png") != std::string::npos, "image.png should be in result");

    // Test deterministic repeat
    std::string result2 = list_files(base_dir.string());
    expect_equal(result2, result, "Repeated call should yield same result");

    // Test malicious inputs safely raise exceptions
    std::vector<std::string> allowed_types_inv_arg = {typeid(std::invalid_argument).name(), typeid(std::runtime_error).name()};
    std::vector<std::string> allowed_types_rt = {typeid(std::runtime_error).name()};
    std::vector<std::string> allowed_types_inv = {typeid(std::invalid_argument).name()};

    assert_raises([]() { list_files("; rm -rf / #"); }, allowed_types_inv_arg);
    assert_raises([]() { list_files("&& echo hacked"); }, allowed_types_inv_arg);
    assert_raises([]() { list_files("/this/path/does/not/exist"); }, allowed_types_rt);
    assert_raises([]() { list_files(""); }, allowed_types_inv);

    // Cleanup
    fs::remove_all(base_dir);

    return 0;
}