#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include <algorithm>
#include <stdexcept>
#include <sstream>
#include <unordered_map>
#include <functional>
#include <fstream>

namespace fs = std::filesystem;

struct RequestArgs {
    std::unordered_map<std::string, std::string> args;

    std::string get(const std::string& key) const {
        auto it = args.find(key);
        if (it != args.end()) {
            return it->second;
        }
        return "";
    }
};

RequestArgs* request = nullptr;

void send_file(const std::string& path, bool as_attachment) {
    std::cout << "Sending file: " << path << " as attachment: " << (as_attachment ? "true" : "false") << std::endl;
}

std::string download() {
    if (request == nullptr) {
        throw std::runtime_error("Request object is not available");
    }

    std::string file = request->get("file");
    if (file.empty()) {
        throw std::invalid_argument("File parameter is missing or empty");
    }

    if (file.find('/') != std::string::npos || file.find('\\') != std::string::npos) {
        throw std::invalid_argument("Invalid file name");
    }

    std::vector<std::string> parts;
    std::string part;
    std::stringstream ss(file);
    while (std::getline(ss, part, '_')) {
        parts.push_back(part);
    }

    for (const auto& p : parts) {
        if (p.empty() || p == "." || p == "..") {
            throw std::invalid_argument("Invalid path component");
        }
    }

    fs::path base_dir = fs::absolute("files");
    fs::path rel_path;
    for (const auto& p : parts) {
        rel_path /= p;
    }
    fs::path abs_path = fs::absolute(base_dir / rel_path);

    auto base_dir_str = base_dir.string();
    auto abs_path_str = abs_path.string();
    
    if (!base_dir_str.empty() && base_dir_str.back() != fs::path::preferred_separator) {
        base_dir_str += fs::path::preferred_separator;
    }

    if (abs_path_str.find(base_dir_str) != 0) {
        throw std::invalid_argument("Path traversal detected");
    }

    if (!fs::is_regular_file(abs_path)) {
        throw std::runtime_error("File not found");
    }

    send_file(abs_path.string(), true);
    return abs_path.string();
}

int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_raises(const std::function<void()>& fn, const std::string& message) {
    try {
        fn();
        fail(message + " (no exception thrown)");
    } catch (const std::exception&) {
        // Expected
    }
}

bool ends_with_slash_files_docs_readme(const std::string& s) {
    std::string target = "/files/docs/readme.txt";
    if (s.size() < target.size()) return false;
    return s.compare(s.size() - target.size(), target.size(), target) == 0;
}

int main() {
    fs::path base = fs::current_path() / "Test" / "CWE-641_sonar_1";
    fs::path files = base / "files" / "docs";
    fs::create_directories(files);
    
    {
        std::ofstream out(files / "readme.txt");
        out << "ok";
    }

    fs::path saved_cwd = fs::current_path();
    fs::current_path(base);

    try {
        // Test 1: Valid file download
        {
            RequestArgs req;
            req.args["file"] = "docs_readme.txt";
            request = &req;
            std::string result = download();
            std::string normalized = result;
            std::replace(normalized.begin(), normalized.end(), '\\', '/');
            expect_true(ends_with_slash_files_docs_readme(normalized), 
                        "Valid file path should end with /files/docs/readme.txt, got: " + normalized);
        }

        // Test 2: Traversal-like segments rejected
        {
            RequestArgs req;
            req.args["file"] = ".._.._etc_passwd";
            request = &req;
            expect_raises(download, "Traversal-like segments should be rejected");
        }

        // Test 3: Missing file rejected
        {
            RequestArgs req;
            req.args["file"] = "docs_missing.txt";
            request = &req;
            expect_raises(download, "Missing file should be rejected");
        }

        // Test 4: Empty file parameter rejected
        {
            RequestArgs req;
            req.args["file"] = "";
            request = &req;
            expect_raises(download, "Empty file parameter should be rejected");
        }

        // Test 5: Null request rejected
        {
            request = nullptr;
            expect_raises(download, "Null request should be rejected");
        }

    } catch (...) {
        fail("Unexpected exception escaped test harness");
    }

    fs::current_path(saved_cwd);
    fs::remove_all(base);

    if (fail_count > 0) {
        std::cerr << fail_count << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}