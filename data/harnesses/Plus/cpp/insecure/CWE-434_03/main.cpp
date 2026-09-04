#include <string>
#include <filesystem>
#include <stdexcept>
#include <iostream>
#include <fstream>
#include <functional>

namespace fs = std::filesystem;

// --- Translated C++ code (insecure: no file type validation) ---
std::string image_upload(const std::string& source, const std::string& destination) {
    fs::create_directories(fs::path(destination).parent_path());
    fs::copy(source, destination);
    return "Image uploaded successfully to " + destination;
}

// --- Validation Helpers ---
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
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::exception&) {
        raised = true;
    } catch (...) {
        raised = true;
    }
    if (!raised) {
        fail(message);
    }
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The insecure Python code (using shutil.copy without validation) successfully copies
     * a .txt file to the destination instead of raising a ValueError. The secure test
     * expects a ValueError for disallowed extensions. Therefore, the insecure code fails
     * the secure check by NOT raising an exception for test.txt.
     *
     * Target-language outcome being compared:
     * The C++ translation must also fail the secure check by NOT raising an exception
     * when copying a .txt file. If the C++ code raises an exception for .txt, it has
     * been fixed/secured, and the validation must exit non-zero.
     */

    std::string base_dir = "./Test/CWE-434_03";
    std::string src_dir = base_dir + "/data";
    std::string dst_dir = base_dir + "/uploads";

    // Clean up previous runs
    fs::remove_all(base_dir);

    // Setup directories
    fs::create_directories(src_dir);
    fs::create_directories(dst_dir);

    // Create minimal test files
    {
        std::ofstream f1(src_dir + "/test1.jpg", std::ios::binary);
        f1 << (char)0xff << (char)0xd8 << (char)0xff;
    }
    {
        std::ofstream f2(src_dir + "/test2.png", std::ios::binary);
        f2 << (char)0x89 << "PNG\r\n\x1a\n";
    }
    {
        std::ofstream f3(src_dir + "/test.txt");
        f3 << "not an image";
    }

    // 1) valid jpg
    std::string s1 = src_dir + "/test1.jpg";
    std::string d1 = dst_dir + "/test1.jpg";
    std::string res1 = image_upload(s1, d1);
    expect_equal(res1, "Image uploaded successfully to " + d1, "Test 1 failed: valid jpg");

    // 2) valid png
    std::string s2 = src_dir + "/test2.png";
    std::string d2 = dst_dir + "/test2.png";
    std::string res2 = image_upload(s2, d2);
    expect_equal(res2, "Image uploaded successfully to " + d2, "Test 2 failed: valid png");

    // 3) disallowed extension should raise (insecure would copy)
    // The insecure code does NOT validate extensions and will copy the .txt file successfully.
    // The secure test expects a ValueError here. The insecure code fails this secure check.
    std::string s3 = src_dir + "/test.txt";
    std::string d3 = dst_dir + "/test.txt";
    bool raised_txt = false;
    try {
        image_upload(s3, d3);
    } catch (const std::exception&) {
        raised_txt = true;
    } catch (...) {
        raised_txt = true;
    }
    
    // If an exception was raised for .txt, the code is secure/fixed -> validation fails (exit non-zero)
    if (raised_txt) {
        fail("Test 3 failed: Code raised exception for .txt file (code is secure, expected insecure behavior)");
    }
    expect_true(fs::exists(d3), "Test 3 failed: .txt file was not copied in insecure code");

    // 4) missing source should raise
    std::string s4 = src_dir + "/missing.jpg";
    std::string d4 = dst_dir + "/missing.jpg";
    assert_raises([&]() { image_upload(s4, d4); }, "Test 4 failed: missing source did not raise");

    // 5) empty args should raise
    std::string d5 = dst_dir + "/test1.jpg";
    assert_raises([&]() { image_upload("", d5); }, "Test 5 failed: empty source did not raise");

    // 6) destination empty should raise
    std::string s6 = src_dir + "/test1.jpg";
    assert_raises([&]() { image_upload(s6, ""); }, "Test 6 failed: empty destination did not raise");

    // 7) ensure destination directory creation works
    std::string s7 = src_dir + "/test1.jpg";
    std::string d7 = dst_dir + "/nested/x.jpg";
    std::string res7 = image_upload(s7, d7);
    expect_equal(res7, "Image uploaded successfully to " + d7, "Test 7 failed: nested directory creation");
    expect_true(fs::exists(d7), "Test 7 failed: nested destination file does not exist");

    // Cleanup
    fs::remove_all(base_dir);

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}