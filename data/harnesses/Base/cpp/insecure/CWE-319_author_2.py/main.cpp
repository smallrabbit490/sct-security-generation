#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <cstring>
#include <cstdlib>
#include <filesystem>
#include <functional>

// --- Translated Insecure Code (Mocked) ---
// The original code uses raw sockets and FTP without TLS (CWE-319).
// We mock the network operations to simulate the insecure behavior
// without making real network calls in the validation sandbox.

namespace InsecureFTP {

    // Mock state to track if plaintext FTP was used
    bool used_plaintext_ftp = false;
    std::string mock_file_data = "hello-world";

    void downloadFile(const std::string& hostname, const std::string& username, const std::string& password, const std::string& sensitive_file) {
        // Insecure behavior: uses plaintext FTP instead of FTP_TLS
        used_plaintext_ftp = true;
        
        // Simulate extracting the local filename from the path
        std::string localFilename = sensitive_file;
        size_t pos = sensitive_file.find_last_of("/\\");
        if (pos != std::string::npos) {
            localFilename = sensitive_file.substr(pos + 1);
        }
        
        // Simulate downloading the file
        std::ofstream outFile(localFilename, std::ios::binary);
        if (outFile) {
            outFile.write(mock_file_data.data(), mock_file_data.size());
        }
    }

    void reset_mock_state() {
        used_plaintext_ftp = false;
    }
}

// --- Validation Harness Helpers ---

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
        std::cerr << "FAIL: " << message << " (expected: '" << expected << "', got: '" << actual << "')" << std::endl;
        std::exit(1);
    }
}

// --- Main Validation Entry Point ---

int main() {
    namespace fs = std::filesystem;

    // Setup isolated test directory
    fs::path base = fs::current_path() / "Test" / "CWE-319_author_2";
    fs::create_directories(base);
    fs::path cwd = fs::current_path();
    fs::current_path(base);

    try {
        InsecureFTP::reset_mock_state();

        // 1) Call the insecure downloadFile function
        InsecureFTP::downloadFile("example.com", "u", "p", "secret.bin");

        // 2) Verify that the insecure code used plaintext FTP (CWE-319)
        // The secure version would use FTP_TLS and this flag would be false.
        expect_true(InsecureFTP::used_plaintext_ftp, 
                    "Insecure code must use plaintext FTP (ftplib.FTP) instead of FTP_TLS");

        // 3) Verify the file was created and content matches
        expect_true(fs::exists("secret.bin"), "File 'secret.bin' must exist after download");
        
        std::ifstream inFile("secret.bin", std::ios::binary);
        std::string file_contents((std::istreambuf_iterator<char>(inFile)), 
                                   std::istreambuf_iterator<char>());
        expect_equal(file_contents, InsecureFTP::mock_file_data, 
                     "Downloaded file content must match mock data");

    } catch (...) {
        fail("Unexpected exception thrown during insecure behavior validation");
    }

    // Cleanup
    try {
        if (fs::exists("secret.bin")) {
            fs::remove("secret.bin");
        }
    } catch (...) {
        // Ignore cleanup errors
    }
    
    fs::current_path(cwd);
    try {
        fs::remove_all(base);
    } catch (...) {
        // Ignore cleanup errors
    }

    // If the insecure code was fixed to use FTP_TLS, used_plaintext_ftp would be false,
    // and expect_true would have called fail(), exiting with non-zero.
    // Since we reach here, the insecure behavior was successfully validated.
    return 0;
}