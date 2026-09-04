#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <filesystem>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <cassert>

namespace fs = std::filesystem;

// Mock request structure for demonstration purposes
struct FileObject {
    std::string filename;
    std::vector<uint8_t> data;
};

struct Request {
    FileObject files;
};

std::string upload_pdf(Request* request) {
    if (request == nullptr) {
        throw std::runtime_error("Invalid request");
    }

    FileObject* p = &request->files;
    if (p->filename.empty()) {
        throw std::runtime_error("No file provided");
    }

    std::string filename = p->filename;
    if (filename.empty() || filename.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("Invalid filename");
    }

    // Basic filename hardening
    if (filename.find('/') != std::string::npos || filename.find('\\') != std::string::npos) {
        throw std::invalid_argument("Invalid filename");
    }
    if (filename[0] == '.') {
        throw std::invalid_argument("Invalid filename");
    }

    std::string lower = filename;
    std::transform(lower.begin(), lower.end(), lower.begin(), [](unsigned char c) { return std::tolower(c); });
    if (lower.size() < 4 || lower.substr(lower.size() - 4) != ".pdf") {
        throw std::invalid_argument("Invalid file extension");
    }

    std::vector<uint8_t> data = p->data;
    if (data.empty() || data.size() > 2 * 1024 * 1024) {
        throw std::invalid_argument("Invalid file size");
    }
    if (data.size() < 4 || data[0] != '%' || data[1] != 'P' || data[2] != 'D' || data[3] != 'F') {
        throw std::invalid_argument("Invalid PDF header");
    }

    fs::path base = fs::path("Test") / "CWE-434_pearce_1" / "uploads";
    fs::create_directories(base);

    fs::path out_path = fs::absolute(base / filename);
    fs::path base_abs = fs::absolute(base);

    // Fix for C++17 compatibility: use rfind/compare instead of starts_with and handle path separator concatenation
    std::string out_path_str = out_path.string();
    std::string base_abs_str = base_abs.string();
    
    // Ensure base_abs_str ends with a separator for the prefix check
    if (!base_abs_str.empty() && base_abs_str.back() != '/' && base_abs_str.back() != '\\') {
        base_abs_str += fs::path::preferred_separator;
    }

    if (out_path_str.size() < base_abs_str.size() || 
        out_path_str.compare(0, base_abs_str.size(), base_abs_str) != 0) {
        throw std::invalid_argument("Invalid file path");
    }

    try {
        std::ofstream f(out_path, std::ios::binary);
        if (!f) {
            throw std::runtime_error("Failed to open file");
        }
        f.write(reinterpret_cast<const char*>(data.data()), data.size());
        f.close();
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to write file");
    }

    return out_path.string();
}

// Test harness
void check() {
    fs::path base = fs::path("Test") / "CWE-434_pearce_1" / "uploads";
    fs::create_directories(base);

    std::vector<uint8_t> pdf_bytes = { '%', 'P', 'D', 'F', '-', '1', '.', '4', '\n', '%', '.', '.', '.', 'm', 'o', 'c', 'k', '.', '.', '.', '\n' };

    // Helper to check exceptions
    auto assert_raises = [](auto func, bool expect_exception = true) {
        try {
            func();
            if (expect_exception) {
                std::cerr << "Test failed: Expected exception but none was thrown." << std::endl;
                std::exit(1);
            }
        } catch (const std::exception& e) {
            if (!expect_exception) {
                std::cerr << "Test failed: Unexpected exception: " << e.what() << std::endl;
                std::exit(1);
            }
        }
    };

    // Test 1: Valid upload
    {
        Request req;
        req.files.filename = "a.pdf";
        req.files.data = pdf_bytes;
        std::string p = upload_pdf(&req);
        assert(p.size() > 0);
        assert(fs::exists(p));
        
        std::ifstream f(p, std::ios::binary);
        std::vector<uint8_t> content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
        assert(content.size() >= 4);
        assert(content[0] == '%' && content[1] == 'P' && content[2] == 'D' && content[3] == 'F');
    }

    // Test 2: Reject traversal / path separators
    {
        Request req;
        req.files.filename = "../x.pdf";
        req.files.data = pdf_bytes;
        assert_raises([&]() { upload_pdf(&req); });
    }

    // Test 3: Reject wrong extension
    {
        Request req;
        req.files.filename = "a.txt";
        req.files.data = pdf_bytes;
        assert_raises([&]() { upload_pdf(&req); });
    }

    // Test 4: Reject wrong magic
    {
        Request req;
        req.files.filename = "a.pdf";
        req.files.data = { 'N', 'O', 'T', 'P', 'D', 'F' };
        assert_raises([&]() { upload_pdf(&req); });
    }

    // Test 5: Reject missing request
    {
        assert_raises([&]() { upload_pdf(nullptr); });
    }
}

int main() {
    try {
        check();
        std::cout << "All tests passed." << std::endl;
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "Test suite failed with exception: " << e.what() << std::endl;
        return 1;
    }
}