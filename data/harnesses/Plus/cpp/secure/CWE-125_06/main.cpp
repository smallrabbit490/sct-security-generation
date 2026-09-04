#include <filesystem>
#include <fstream>
#include <string>
#include <stdexcept>
#include <iostream>
#include <cstdlib>

namespace fs = std::filesystem;

std::string read_file_at_position(const std::string& file_path, int start_position, int length, const std::string& base_directory) {
    if (start_position < 0 || length < 0) {
        throw std::invalid_argument("start_position and length must be non-negative");
    }

    // Require simple file name to avoid separators
    if (fs::path(file_path).filename() != file_path) {
        throw std::invalid_argument("file_path must be a simple file name");
    }

    fs::path base_abs = fs::absolute(base_directory);
    fs::path full_path = fs::absolute(base_abs / file_path);

    // Prevent path traversal
    std::string base_str = base_abs.string();
    std::string full_str = full_path.string();
    char sep = fs::path::preferred_separator;
    if (full_str.rfind(base_str + sep, 0) != 0) {
        throw std::invalid_argument("invalid path");
    }

    std::ifstream f(full_path, std::ios::binary);
    if (!f) {
        throw std::runtime_error("failed to open file");
    }

    f.seekg(0, std::ios::end);
    auto size = f.tellg();
    if (start_position > size || static_cast<long long>(start_position) + length > size) {
        throw std::out_of_range("read out of range");
    }

    f.seekg(start_position);
    std::string data(length, '\0');
    f.read(&data[0], length);

    return data;
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
        std::cerr << "FAIL: " << message << " (expected '" << expected << "', got '" << actual << "')" << std::endl;
        std::exit(1);
    }
}

template<typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    }
}

int main() {
    std::string base_directory = "./Test/CWE-125_06";
    fs::create_directories(base_directory);
    
    fs::path fp = fs::path(base_directory) / "data.txt";
    {
        std::ofstream f(fp, std::ios::binary);
        if (!f) {
            fail("Failed to open test file for writing");
        }
        f << "0123456789HelloWorld";
    }

    expect_equal(read_file_at_position("data.txt", 10, 5, base_directory), "Hello", "Test 1");
    expect_equal(read_file_at_position("data.txt", 0, 4, base_directory), "0123", "Test 2");
    expect_equal(read_file_at_position("data.txt", 15, 5, base_directory), "World", "Test 3");

    // out-of-range must raise
    assert_raises([&]() {
        read_file_at_position("data.txt", 100, 5, base_directory);
    }, "Out of range start_position");

    assert_raises([&]() {
        read_file_at_position("data.txt", 10, 999, base_directory);
    }, "Out of range length");

    // invalid inputs must raise
    assert_raises([&]() {
        read_file_at_position("data.txt", -1, 1, base_directory);
    }, "Negative start_position");

    assert_raises([&]() {
        read_file_at_position("../data.txt", 0, 1, base_directory);
    }, "Path traversal attempt");

    // Cleanup
    fs::remove_all(base_directory);

    std::cout << "All tests passed!" << std::endl;
    return 0;
}