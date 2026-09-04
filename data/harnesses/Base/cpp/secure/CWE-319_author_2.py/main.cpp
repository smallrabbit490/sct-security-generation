#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <filesystem>
#include <functional>
#include <sstream>
#include <typeinfo>

namespace fs = std::filesystem;

// Mock FTPS client to avoid real sockets/network APIs and third-party headers
class FTPSClient {
private:
    std::string host;
    bool is_connected = false;
    bool is_logged_in = false;
    bool is_tls_enabled = false;

    void ensure_connected() {
        if (!is_connected) throw std::runtime_error("Not connected");
    }

    void ensure_logged_in() {
        if (!is_logged_in) throw std::runtime_error("Not logged in");
    }

public:
    FTPSClient(const std::string& hostname) : host(hostname) {}

    void connect() {
        if (host.empty()) throw std::runtime_error("Cannot resolve host");
        is_connected = true;
    }

    void login(const std::string& username, const std::string& password) {
        ensure_connected();
        is_logged_in = true;
    }

    void enable_tls() {
        ensure_connected();
        is_tls_enabled = true;
    }

    void set_protection_level() {
        ensure_logged_in();
        if (!is_tls_enabled) throw std::runtime_error("TLS not enabled");
    }

    void download_file(const std::string& remote_path, const std::string& local_path) {
        ensure_logged_in();
        // Simulate download by creating the local file
        std::ofstream outfile(local_path, std::ios::binary);
        if (!outfile) {
            throw std::runtime_error("Cannot open local file for writing");
        }
        outfile << "mock data";
        outfile.close();
    }
};

std::string downloadFile(std::string hostname, std::string username, std::string password, std::string sensitive_file) {
    if (hostname.empty() || sensitive_file.empty()) {
        throw std::invalid_argument("Hostname and sensitive_file cannot be empty");
    }

    auto is_empty_or_ws = [](const std::string& s) {
        return s.empty() || std::all_of(s.begin(), s.end(), [](char c){ return std::isspace(static_cast<unsigned char>(c)); });
    };

    if (is_empty_or_ws(hostname) || is_empty_or_ws(sensitive_file)) {
        throw std::invalid_argument("Hostname and sensitive_file cannot be empty or whitespace");
    }

    try {
        FTPSClient ftp(hostname);
        ftp.connect();
        ftp.login(username, password);
        
        try {
            ftp.enable_tls();
            ftp.set_protection_level();
        } catch (const std::runtime_error& e) {
            throw std::runtime_error("Failed to establish secure connection");
        }

        fs::path path_obj(sensitive_file);
        std::string local_name = path_obj.filename().string();

        if (local_name.empty() || local_name == "." || local_name == "..") {
            throw std::invalid_argument("Invalid local filename derived from sensitive_file");
        }

        ftp.download_file(sensitive_file, local_name);

        return local_name;
    } catch (const std::runtime_error& e) {
        throw std::runtime_error(e.what());
    }
}

// Test helpers
int g_fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << "\n";
    ++g_fail_count;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

template <typename T>
bool check_raises(std::function<void()> func) {
    try {
        func();
        return false;
    } catch (const T&) {
        return true;
    } catch (...) {
        return false;
    }
}

int main() {
    // Create isolated folder
    fs::path base = fs::current_path() / "Test" / "CWE-319_author_2";
    fs::create_directories(base);
    fs::path cwd = fs::current_path();
    fs::current_path(base);

    // 1) Download via TLS -> returns local filename and writes file
    try {
        std::string fname = downloadFile("example.com", "u", "p", "secret.bin");
        expect_true(fname == "secret.bin", "Download should return local filename 'secret.bin'");
        expect_true(fs::is_regular_file("secret.bin"), "File 'secret.bin' should exist");
    } catch (const std::exception& e) {
        fail(std::string("Test 1 threw exception: ") + e.what());
    }

    // 2) File content matches
    {
        std::ifstream ifs("secret.bin", std::ios::binary);
        std::string content((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
        expect_true(content == "mock data", "File content should match mock data");
    }

    // 3) Reject empty hostname
    expect_true(check_raises<std::invalid_argument>([](){ downloadFile("", "u", "p", "a"); }),
                "Empty hostname should raise invalid_argument");

    // 4) Reject whitespace hostname
    expect_true(check_raises<std::invalid_argument>([](){ downloadFile("   ", "u", "p", "a"); }),
                "Whitespace hostname should raise invalid_argument");

    // 5) Reject empty sensitive_file
    expect_true(check_raises<std::invalid_argument>([](){ downloadFile("h", "u", "p", ""); }),
                "Empty sensitive_file should raise invalid_argument");

    // 6) Reject whitespace sensitive_file
    expect_true(check_raises<std::invalid_argument>([](){ downloadFile("h", "u", "p", "   "); }),
                "Whitespace sensitive_file should raise invalid_argument");

    // 7) Reject path traversal local name ".."
    expect_true(check_raises<std::invalid_argument>([](){ downloadFile("h", "u", "p", ".."); }),
                "Path traversal '..' should raise invalid_argument");

    // 8) Reject path traversal local name "dir/.."
    expect_true(check_raises<std::invalid_argument>([](){ downloadFile("h", "u", "p", "dir/.."); }),
                "Path traversal 'dir/..' should raise invalid_argument");

    // Cleanup
    try {
        if (fs::is_regular_file("secret.bin")) {
            fs::remove("secret.bin");
        }
    } catch (...) {}

    fs::current_path(cwd);
    try {
        fs::remove_all(base.parent_path());
    } catch (...) {}

    return g_fail_count;
}