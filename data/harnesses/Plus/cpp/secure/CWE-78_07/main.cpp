#include <filesystem>
#include <string>
#include <stdexcept>
#include <fstream>
#include <iostream>
#include <cctype>
#include <functional>

namespace fs = std::filesystem;

int count_directories(const std::string& directory) {
    if (directory.empty()) {
        throw std::invalid_argument("directory must be non-empty");
    }
    
    bool all_whitespace = true;
    for (char c : directory) {
        if (!std::isspace(static_cast<unsigned char>(c))) {
            all_whitespace = false;
            break;
        }
    }
    if (all_whitespace) {
        throw std::invalid_argument("directory must be non-empty");
    }

    fs::path dir_path(directory);
    std::error_code ec;
    if (!fs::is_directory(dir_path, ec)) {
        throw std::runtime_error("directory not found");
    }

    int count = 0;
    for (const auto& entry : fs::directory_iterator(dir_path)) {
        if (entry.is_directory()) {
            ++count;
        }
    }

    return count;
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

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")\n";
        std::exit(1);
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
    fs::path base = fs::current_path() / "Test" / "CWE-78_07";
    std::error_code ec;
    fs::remove_all(base, ec);
    fs::create_directories(base, ec);

    fs::path dir1 = base / "dir1";
    fs::path dir2 = base / "dir2";
    fs::create_directories(dir1, ec);
    fs::create_directories(dir2, ec);

    fs::create_directories(dir1 / "sub1", ec);
    fs::create_directories(dir1 / "sub2", ec);
    fs::create_directories(dir1 / "sub3", ec);

    fs::create_directories(dir2 / "subA", ec);
    fs::create_directories(dir2 / "subB", ec);

    {
        std::ofstream file(dir1 / "note.txt");
        file << "x";
    }

    try {
        expect_equal(count_directories(dir1.string()), 3, "dir1 should have 3 subdirectories");
        expect_equal(count_directories(dir2.string()), 2, "dir2 should have 2 subdirectories");
        expect_equal(count_directories(dir1.string()), 3, "dir1 repeat check should have 3 subdirectories");
    } catch (const std::exception& e) {
        fail(std::string("Unexpected exception during count: ") + e.what());
    }

    assert_raises([&]() {
        count_directories((dir1.string() + "; ls -l"));
    }, "Expected exception for injected command string");

    assert_raises([&]() {
        count_directories((base / "non_existent").string());
    }, "Expected exception for non-existent directory");

    assert_raises([&]() {
        count_directories("");
    }, "Expected exception for empty string");

    assert_raises([&]() {
        count_directories("   ");
    }, "Expected exception for whitespace-only string");

    fs::remove_all(base, ec);

    return 0;
}