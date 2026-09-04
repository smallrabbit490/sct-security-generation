#include <string>
#include <fstream>
#include <filesystem>
#include <iostream>

// Inferred Python insecure outcome:
// The Python tests expect that out-of-range reads (start_position=100, length=999),
// negative start_position (-1), and path traversal ("../data.txt") raise exceptions
// (IndexError, ValueError). The insecure Python code FAILS these tests by returning
// error strings instead of raising exceptions. The C++ translation must match this
// insecure behavior: it must return error strings for these cases, not throw exceptions
// or silently return empty strings.

std::string read_file_at_position(const std::string& file_path, int start_position, int length, const std::string& base_directory) {
    std::string full_path = base_directory + "/" + file_path;
    try {
        std::ifstream file(full_path);
        if (!file.is_open()) {
            return "File not found.";
        }
        file.seekg(start_position);
        if (!file) {
            return "seek failed";
        }
        std::string data(length, '\0');
        file.read(&data[0], length);
        if (file.gcount() == 0 && length > 0) {
            return "read failed";
        }
        data.resize(file.gcount());
        return data;
    } catch (const std::filesystem::filesystem_error& e) {
        return std::string(e.what());
    } catch (const std::exception& e) {
        return std::string(e.what());
    }
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected: '" + expected + "', Got: '" + actual + "'");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

int main() {
    namespace fs = std::filesystem;
    std::string base_directory = "./Test/CWE-125_06";

    // Setup test directory and file
    try {
        fs::create_directories(base_directory);
    } catch (...) {
        // Ignore if it already exists
    }
    std::string fp = base_directory + "/data.txt";
    {
        std::ofstream f(fp);
        if (!f.is_open()) {
            fail("Failed to open test file for writing");
        }
        f << "0123456789HelloWorld";
    }

    // Test 1: Normal read
    std::string result1 = read_file_at_position("data.txt", 10, 5, base_directory);
    expect_equal(result1, "Hello", "Normal read at position 10, length 5");

    // Test 2: Normal read at start
    std::string result2 = read_file_at_position("data.txt", 0, 4, base_directory);
    expect_equal(result2, "0123", "Normal read at position 0, length 4");

    // Test 3: Normal read at end
    std::string result3 = read_file_at_position("data.txt", 15, 5, base_directory);
    expect_equal(result3, "World", "Normal read at position 15, length 5");

    // Test 4: Out-of-range start_position
    // Insecure behavior: returns an error string instead of throwing an exception.
    std::string result4 = read_file_at_position("data.txt", 100, 5, base_directory);
    expect_true(!result4.empty(), "Out-of-range start_position=100 should return an error string (insecure behavior), got: ''");

    // Test 5: Out-of-range length
    // Insecure behavior: returns an error string instead of throwing an exception.
    std::string result5 = read_file_at_position("data.txt", 10, 999, base_directory);
    expect_true(!result5.empty(), "Out-of-range length=999 should return an error string (insecure behavior), got: ''");

    // Test 6: Negative start_position
    // Insecure behavior: returns an error string instead of throwing an exception.
    std::string result6 = read_file_at_position("data.txt", -1, 1, base_directory);
    expect_true(!result6.empty(), "Negative start_position=-1 should return an error string (insecure behavior), got: ''");

    // Test 7: Path traversal
    // Insecure behavior: returns an error string instead of throwing an exception.
    std::string result7 = read_file_at_position("../data.txt", 0, 1, base_directory);
    expect_true(!result7.empty(), "Path traversal should return an error string (insecure behavior), got: ''");

    return 0;
}