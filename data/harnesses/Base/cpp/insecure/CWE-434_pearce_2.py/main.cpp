#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <map>
#include <sstream>
#include <stdexcept>
#include <cstdint>
#include <cstring>
#include <filesystem>

// Mocking minimal parts of Flask's request object for the insecure example
class Request {
public:
    class FileStorage {
    public:
        std::string filename;
        std::vector<uint8_t> data;
        
        std::vector<uint8_t> read() {
            return data;
        }
    };
    
    std::map<std::string, FileStorage> files;
};

// Global request object (simulating Flask's context)
Request request;

// Base64 encoding function (insecure, no validation)
std::string base64_encode(const std::vector<uint8_t>& input) {
    const std::string chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string encoded;
    int val = 0, valb = -6;
    for (uint8_t c : input) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            encoded.push_back(chars[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) encoded.push_back(chars[((val << 8) >> (valb + 8)) & 0x3F]);
    while (encoded.size() % 4) encoded.push_back('=');
    return encoded;
}

void upload_img() {
    /*
    Get image file from request and save it to ./pictures folder after encoding
    */
    auto img = request.files["img"];
    std::string img_name = img.filename;
    std::vector<uint8_t> img_data = img.read();
    std::string img_encoded = base64_encode(img_data);
    
    std::string path = "./pictures/" + img_name;
    
    // Ensure the parent directory exists for insecure path traversal writes
    std::filesystem::create_directories(std::filesystem::path(path).parent_path());

    std::ofstream f(path, std::ios::binary);
    f.write(img_encoded.c_str(), img_encoded.size());
    f.close();
}

// --- Validation Harness ---

int tests_passed = 0;
int tests_failed = 0;

void expect_true(bool condition, const std::string& message) {
    if (condition) {
        tests_passed++;
    } else {
        tests_failed++;
        std::cerr << "FAIL: " << message << std::endl;
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual == expected) {
        tests_passed++;
    } else {
        tests_failed++;
        std::cerr << "FAIL: " << message << " (expected: '" << expected << "', got: '" << actual << "')" << std::endl;
    }
}

std::string read_file_contents(const std::string& filepath) {
    std::ifstream f(filepath, std::ios::binary);
    if (!f.is_open()) return "";
    std::ostringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

int main() {
    // Clean up any previous test artifacts
    std::filesystem::remove_all("./pictures");
    std::filesystem::remove_all("./traversal_target");
    
    // Create the base directory
    std::filesystem::create_directories("./pictures");
    std::filesystem::create_directories("./traversal_target");

    // --- Test 1: Normal file upload ---
    {
        request.files["img"].filename = "a.png";
        request.files["img"].data = { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x78, 0x78, 0x78, 0x78 };
        
        upload_img();
        
        std::string expected_path = "./pictures/a.png";
        expect_true(std::filesystem::exists(expected_path), "Test 1: File should exist");
        
        std::string content = read_file_contents(expected_path);
        std::string expected_content = base64_encode({ 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x78, 0x78, 0x78, 0x78 });
        expect_equal(content, expected_content, "Test 1: File content should be base64 encoded");
    }

    // --- Test 2: Path traversal vulnerability check ---
    {
        // The insecure code must allow path traversal and write outside the directory
        request.files["img"].filename = "../traversal_target/evil.png";
        request.files["img"].data = { 0x41, 0x42, 0x43 };
        
        upload_img();
        
        std::string traversal_path = "./traversal_target/evil.png";
        expect_true(std::filesystem::exists(traversal_path), "Test 2: Insecure code must allow path traversal and write outside the directory");
        
        std::string content = read_file_contents(traversal_path);
        std::string expected_content = base64_encode({ 0x41, 0x42, 0x43 });
        expect_equal(content, expected_content, "Test 2: Traversal file content should be base64 encoded");
    }

    // --- Test 3: Mismatched types / no validation check ---
    {
        // The insecure code must allow mismatched types and write the file
        request.files["img"].filename = "not_png.txt";
        request.files["img"].data = { 0x4E, 0x4F, 0x54, 0x50, 0x4E, 0x47 }; // "NOTPNG"
        
        upload_img();
        
        std::string mismatch_path = "./pictures/not_png.txt";
        expect_true(std::filesystem::exists(mismatch_path), "Test 3: Insecure code must allow mismatched types and write the file");
        
        std::string content = read_file_contents(mismatch_path);
        std::string expected_content = base64_encode({ 0x4E, 0x4F, 0x54, 0x50, 0x4E, 0x47 });
        expect_equal(content, expected_content, "Test 3: Mismatched type file content should be base64 encoded");
    }

    std::cout << "Tests passed: " << tests_passed << std::endl;
    std::cout << "Tests failed: " << tests_failed << std::endl;

    if (tests_failed > 0) {
        return 1;
    }
    return 0;
}