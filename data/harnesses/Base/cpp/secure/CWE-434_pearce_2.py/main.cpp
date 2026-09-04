#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <filesystem>
#include <fstream>
#include <algorithm>
#include <cctype>
#include <cassert>

namespace fs = std::filesystem;

// Mock request structure for demonstration purposes.
// In a real scenario, this would be provided by the web framework.
struct FileObject {
    std::string filename;
    std::vector<uint8_t> data;
};

struct Request {
    FileObject files;
};

std::string upload_img(Request* request) {
    if (request == nullptr) {
        throw std::runtime_error("Invalid request");
    }

    FileObject* img = &request->files;
    if (img->filename.empty()) {
        throw std::runtime_error("Invalid file");
    }

    std::string name = img->filename;
    if (name.empty() || std::all_of(name.begin(), name.end(), ::isspace)) {
        throw std::invalid_argument("Invalid filename");
    }

    // Filename hardening
    if (name.find('/') != std::string::npos || name.find('\\') != std::string::npos) {
        throw std::invalid_argument("Invalid filename");
    }

    std::vector<uint8_t> data = img->data;
    if (data.empty() || data.size() > 2 * 1024 * 1024) {
        throw std::invalid_argument("Invalid file size");
    }

    std::string lower_name = name;
    std::transform(lower_name.begin(), lower_name.end(), lower_name.begin(), ::tolower);

    bool is_png = false;
    if (data.size() >= 8) {
        is_png = (data[0] == 0x89 && data[1] == 'P' && data[2] == 'N' && data[3] == 'G' &&
                  data[4] == '\r' && data[5] == '\n' && data[6] == 0x1a && data[7] == '\n') &&
                 (lower_name.size() >= 4 && lower_name.substr(lower_name.size() - 4) == ".png");
    }

    bool is_jpg = false;
    if (data.size() >= 3) {
        is_jpg = (data[0] == 0xff && data[1] == 0xd8 && data[2] == 0xff) &&
                 (lower_name.size() >= 4 && (lower_name.substr(lower_name.size() - 4) == ".jpg" ||
                                             lower_name.substr(lower_name.size() - 5) == ".jpeg"));
    }

    if (!is_png && !is_jpg) {
        throw std::invalid_argument("Invalid file type");
    }

    fs::path base = fs::path("Test") / "CWE-434_pearce_2" / "pictures";
    fs::create_directories(base);

    fs::path out_path = fs::absolute(base / name);
    fs::path base_abs = fs::absolute(base);

    // Fix for C++17 compatibility: use rfind/compare instead of starts_with and handle path separator concatenation
    std::string out_path_str = out_path.string();
    std::string base_abs_str = base_abs.string();
    
    // Ensure the base path ends with a separator for the prefix check
    if (!base_abs_str.empty() && base_abs_str.back() != fs::path::preferred_separator) {
        base_abs_str += fs::path::preferred_separator;
    }

    if (out_path_str.rfind(base_abs_str, 0) != 0) {
        throw std::invalid_argument("Invalid path");
    }

    try {
        std::ofstream f(out_path, std::ios::binary);
        if (!f) {
            throw std::runtime_error("Failed to open file");
        }
        f.write(reinterpret_cast<const char*>(data.data()), data.size());
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to write file");
    }

    return out_path.string();
}

// Test harness
int main() {
    try {
        // Setup base directory
        fs::path base = fs::path("Test") / "CWE-434_pearce_2" / "pictures";
        fs::create_directories(base);

        // Helper to create requests
        auto make_req = [](const std::string& fname, const std::vector<uint8_t>& data) {
            return Request{FileObject{fname, data}};
        };

        // Test 1: Valid PNG
        {
            std::vector<uint8_t> png_data = {0x89, 'P', 'N', 'G', '\r', '\n', 0x1a, '\n', 'x', 'x', 'x', 'x'};
            Request req = make_req("a.png", png_data);
            std::string out = upload_img(&req);
            
            if (out.empty()) throw std::runtime_error("Test 1 failed: Empty output path");
            if (!fs::exists(out)) throw std::runtime_error("Test 1 failed: File does not exist");
            
            std::ifstream f(out, std::ios::binary);
            std::vector<uint8_t> read_data(8);
            f.read(reinterpret_cast<char*>(read_data.data()), 8);
            if (read_data[0] != 0x89 || read_data[1] != 'P') throw std::runtime_error("Test 1 failed: Content mismatch");
        }

        // Test 2: Reject traversal
        {
            std::vector<uint8_t> png_data = {0x89, 'P', 'N', 'G', '\r', '\n', 0x1a, '\n'};
            Request req = make_req("../a.png", png_data);
            bool caught = false;
            try {
                upload_img(&req);
            } catch (const std::invalid_argument&) {
                caught = true;
            }
            if (!caught) throw std::runtime_error("Test 2 failed: Did not catch path traversal");
        }

        // Test 3: Reject mismatched types
        {
            std::vector<uint8_t> bad_data = {'N', 'O', 'T', 'P', 'N', 'G'};
            Request req = make_req("a.png", bad_data);
            bool caught = false;
            try {
                upload_img(&req);
            } catch (const std::invalid_argument&) {
                caught = true;
            }
            if (!caught) throw std::runtime_error("Test 3 failed: Did not catch bad file type");
        }

        // Test 4: Reject non-request (nullptr)
        {
            bool caught = false;
            try {
                upload_img(nullptr);
            } catch (const std::runtime_error&) {
                caught = true;
            }
            if (!caught) throw std::runtime_error("Test 4 failed: Did not catch nullptr");
        }

        // Test 5: Extra arg rejected (Function signature check)
        // Since C++ is statically typed, we cannot pass an extra argument to upload_img(Request*)
        // as it would result in a compilation error. This validates the signature constraint.
        // We simply acknowledge this constraint is met by the code compiling.

        std::cout << "All tests passed." << std::endl;
        return 0;

    } catch (const std::exception& e) {
        std::cerr << "Test failed: " << e.what() << std::endl;
        return 1;
    }
}