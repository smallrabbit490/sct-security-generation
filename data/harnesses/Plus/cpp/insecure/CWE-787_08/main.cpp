#include <string>
#include <vector>
#include <iostream>
#include <cstdlib>
#include <csignal>

// --- Translated C++ code (insecure) ---
std::string store_blog_post(const std::string& user_input, int post_length) {
    std::vector<char> post_storage(post_length); // Dynamically allocate memory based on post_length
    for (size_t i = 0; i < user_input.length(); ++i) {
        post_storage[i] = user_input[i]; // Unsafe: Potential out-of-bounds write
    }
    return "Blog post stored successfully.";
}

// --- Validation Harness ---
bool crash_detected = false;

void signal_handler(int signum) {
    crash_detected = true;
    std::_Exit(0); // Exit with 0 to indicate the insecure crash was successfully detected
}

void fail(const char* message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const char* message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const char* message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected '" << expected << "', got '" << actual << "')" << std::endl;
        std::exit(1);
    }
}

int main() {
    // Install signal handler to catch the out-of-bounds assertion/crash
    std::signal(SIGABRT, signal_handler);

    // Inferred Python insecure outcome:
    // The Python code raises an IndexError when user_input exceeds post_length.
    // The C++ insecure translation should similarly crash/fail (e.g., SIGABRT from 
    // vector bounds checking) when attempting the out-of-bounds write.
    // Target-language outcome being compared:
    // We expect the C++ code to crash/abort on the out-of-bounds access. If it does, 
    // the signal handler will exit with 0. If it does NOT crash (meaning the vulnerability 
    // was fixed or safely handled), we fall through and exit with 1.

    // 1) fits within storage
    expect_equal(store_blog_post("Safe content.", 20), "Blog post stored successfully.", "Test 1 failed");
    
    // 2) exactly fits storage
    expect_equal(store_blog_post("abcd", 4), "Blog post stored successfully.", "Test 2 failed");
    
    // 3) empty input
    expect_equal(store_blog_post("", 0), "Blog post stored successfully.", "Test 3 failed");
    
    // 4) larger capacity than needed
    expect_equal(store_blog_post("Hi", 10), "Blog post stored successfully.", "Test 4 failed");

    // 5) exceeds storage must raise/crash (insecure raises IndexError during write)
    // If the code is insecure, it will trigger an out-of-bounds write, causing an 
    // assertion failure and SIGABRT. The signal handler will then exit(0).
    // If the code is secure (e.g., bounds check prevents the write), it will return 
    // normally, and we will reach the fail() below, causing exit(1).
    store_blog_post("This post is too long and unsafe.", 20);
    
    // If we reach here, the out-of-bounds write did NOT crash the program.
    // This means the vulnerability was fixed or safely handled, so we fail the validation.
    fail("Expected a crash (out-of-bounds write) but the function returned normally.");

    return 1;
}