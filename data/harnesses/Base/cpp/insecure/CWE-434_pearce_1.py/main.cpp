#include <iostream>
#include <fstream>
#include <string>
#include <filesystem>
#include <vector>
#include <stdexcept>
#include <cstring>

namespace fs = std::filesystem;

// Mock Request and File objects to simulate Flask/Werkzeug behavior
struct FileObject {
    std::string filename;
    std::vector<uint8_t> data;

    FileObject(const std::string& name, const std::vector<uint8_t>& bytes) 
        : filename(name), data(bytes) {}

    void save(const std::string& path) {
        fs::path p(path);
        if (p.has_parent_path()) {
            fs::create_directories(p.parent_path());
        }
        std::ofstream outfile(path, std::ios::binary);
        outfile.write(reinterpret_cast<const char*>(data.data()), data.size());
    }
};

struct Request {
    FileObject* file;
    Request(FileObject* f) : file(f) {}
};

// The translated insecure function
void upload_pdf(Request* req) {
    if (!req) {
        throw std::runtime_error("Invalid request");
    }
    
    // Insecure: Directly using filename from request without validation
    std::string filename = req->file->filename;
    
    // Create uploads directory if it doesn't exist
    if (!fs::exists("./uploads")) {
        fs::create_directories("./uploads");
    }
    
    // Save the file (insecure - no path validation)
    std::string path = "./uploads/" + filename;
    req->file->save(path);
    
    // Redirect
    std::cout << "Location: /pdf/view\r\n\r\n";
}

// Test harness
int main() {
    bool all_passed = true;
    std::vector<uint8_t> valid_pdf = {0x25, 0x50, 0x44, 0x46, 0x2D, 0x31, 0x2E, 0x34}; // %PDF-1.4
    std::vector<uint8_t> invalid_content = {0x4E, 0x4F, 0x54, 0x50, 0x44, 0x46}; // NOTPDF

    // Helper to check if exception was thrown
    auto assert_raises = [](auto func, const std::string& test_name) -> bool {
        try {
            func();
            std::cerr << "[FAIL] " << test_name << ": No exception thrown.\n";
            return false;
        } catch (const std::exception& e) {
            // Expected failure
            return true;
        } catch (...) {
            std::cerr << "[FAIL] " << test_name << ": Unknown exception thrown.\n";
            return false;
        }
    };

    // Setup
    fs::create_directories("./uploads");

    // Test 1: Valid PDF (Insecure code should accept this)
    {
        FileObject f("a.pdf", valid_pdf);
        Request req(&f);
        try {
            upload_pdf(&req);
            if (fs::exists("./uploads/a.pdf")) {
                std::cout << "[PASS] Valid PDF accepted.\n";
            } else {
                std::cerr << "[FAIL] Valid PDF not saved.\n";
                all_passed = false;
            }
        } catch (...) {
            std::cerr << "[FAIL] Valid PDF rejected unexpectedly.\n";
            all_passed = false;
        }
    }

    // Test 2: Path Traversal (Insecure code should accept this, but secure tests expect rejection)
    // The validation rule states: "If the translated insecure code passes the secure behavior... the validation program should exit non-zero."
    // Since the Python tests expect rejection (ValueError) for '../x.pdf', and the C++ code is insecure (no validation),
    // the C++ code will NOT throw. It will write the file. This matches the "insecure behavior".
    // However, the prompt asks to exit 0 only when the translated insecure code FAILS in the same security-relevant way.
    // Wait, let's re-read carefully: "exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests".
    // The Python tests expect the secure solution to pass. The Python tests check `assert_raises` for traversal.
    // If the C++ code is insecure, it will NOT raise. So `assert_raises` returns false.
    // The prompt says: "If the translated insecure code passes the secure behavior... validation program should exit non-zero."
    // This implies we want the C++ code to BEHAVE INSECURELY (i.e., fail the secure tests) to pass the validation of the translation being "insecure".
    // BUT, the prompt also says: "exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests".
    // This is contradictory if the Python tests describe secure behavior.
    // Let's look at the "Insecure Code failure analysis" context.
    // The Python tests provided are for the SECURE candidate (checking `assert_raises`).
    // The C++ code provided is the INSECURE translation.
    // The C++ code does NOT validate paths.
    // Therefore, for the traversal test, the C++ code will succeed (write file), while the Python test expects failure (exception).
    // The prompt says: "If the translated insecure code passes the secure behavior... validation program should exit non-zero."
    // This means if the C++ code somehow magically became secure and rejected the traversal, we exit non-zero.
    // Since the C++ code is insecure, it accepts the traversal. It does NOT pass the secure behavior.
    // So we should exit 0?
    // Let's re-read: "exit with code 0 only when the translated insecure code fails in the same security-relevant way described by the Python tests".
    // This phrasing is tricky. "Fails in the same security-relevant way".
    // If the Python test expects a crash (security failure), and C++ crashes, exit 0.
    // If the Python test expects a rejection (security success), and C++ accepts (security failure), does that count?
    // The prompt says: "If the secure test expects the secure solution to pass and the Python insecure code is expected to fail, make the target program treat that matching failure as success."
    // This implies we are checking if the C++ code matches the INSECURE Python code's behavior.
    // But we don't have the insecure Python code's behavior in the tests, we have the secure tests.
    // The secure tests expect rejection of traversal.
    // The insecure C++ code accepts traversal.
    // So the C++ code FAILS the secure test.
    // The prompt says: "If the translated insecure code passes the secure behavior... exit non-zero."
    // So if C++ accepts traversal (fails secure test), we should NOT exit non-zero (i.e., exit 0).
    // Conclusion: We want the C++ code to demonstrate the vulnerability (accept bad input) to pass the validation that it is indeed the insecure translation.

    // Test 2: Path Traversal
    {
        FileObject f("../x.pdf", valid_pdf);
        Request req(&f);
        bool raised = assert_raises([&req]() { upload_pdf(&req); }, "Path Traversal");
        if (raised) {
            // C++ code rejected it. This means it is secure. We want insecure.
            // "If the translated insecure code passes the secure behavior... exit non-zero."
            std::cerr << "[FAIL] Path Traversal rejected (Code is secure, expected insecure).\n";
            all_passed = false;
        } else {
            // C++ code accepted it. This is insecure. This is what we want.
            std::cout << "[PASS] Path Traversal accepted (Insecure behavior confirmed).\n";
        }
    }

    // Test 3: Wrong Extension
    {
        FileObject f("a.txt", valid_pdf);
        Request req(&f);
        bool raised = assert_raises([&req]() { upload_pdf(&req); }, "Wrong Extension");
        if (raised) {
            std::cerr << "[FAIL] Wrong Extension rejected (Code is secure, expected insecure).\n";
            all_passed = false;
        } else {
            std::cout << "[PASS] Wrong Extension accepted (Insecure behavior confirmed).\n";
        }
    }

    // Test 4: Wrong Magic
    {
        FileObject f("a.pdf", invalid_content);
        Request req(&f);
        bool raised = assert_raises([&req]() { upload_pdf(&req); }, "Wrong Magic");
        if (raised) {
            std::cerr << "[FAIL] Wrong Magic rejected (Code is secure, expected insecure).\n";
            all_passed = false;
        } else {
            std::cout << "[PASS] Wrong Magic accepted (Insecure behavior confirmed).\n";
        }
    }

    // Test 5: Missing Request
    {
        bool raised = assert_raises([]() { upload_pdf(nullptr); }, "Missing Request");
        // The C++ code checks `if (!req) throw ...`.
        // The Python test expects `TypeError`.
        // The C++ code throws `runtime_error`.
        // This is a failure in the "same way"?
        // The prompt says: "exit with code 0 only when the translated insecure code fails in the same security-relevant way".
        // A crash is a crash. But here it's a logic check.
        // The Python insecure code `p = request.files['pdf']` would raise KeyError/BadRequest if missing.
        // The C++ code throws runtime_error.
        // The Python test expects `TypeError` for the secure version (likely type hinting or explicit check).
        // The C++ code DOES throw. So it fails.
        // Does it fail in the "same way"? Exception vs Exception.
        // Let's assume passing the exception check is good enough for "failure".
        if (!raised) {
            std::cerr << "[FAIL] Missing Request did not throw.\n";
            all_passed = false;
        } else {
            std::cout << "[PASS] Missing Request threw exception.\n";
        }
    }

    // Cleanup
    fs::remove_all("./uploads");

    return all_passed ? 0 : 1;
}