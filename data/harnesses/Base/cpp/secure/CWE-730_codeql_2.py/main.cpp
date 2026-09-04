#include <iostream>
#include <string>
#include <vector>
#include <regex>
#include <stdexcept>
#include <map>
#include <typeinfo>

// Mock request object to simulate Flask's request.args
struct Request {
    std::map<std::string, std::string> args;
};

// Global request object (simulating Flask's global request)
Request request;

bool _is_risky_regex(const std::string& pat) {
    if (pat.size() > 64) {
        return true;
    }
    std::vector<std::string> risky = {"(.+)+", "(.*)+", "(a+)+", "++", "{", "}"};
    for (const auto& x : risky) {
        if (pat.find(x) != std::string::npos) {
            return true;
        }
    }
    return false;
}

bool direct() {
    // Check if pattern and text are in args
    if (request.args.find("pattern") == request.args.end() || 
        request.args.find("text") == request.args.end()) {
        throw std::invalid_argument("Missing pattern or text");
    }
    
    // Get pattern and text
    std::string pattern = request.args["pattern"];
    std::string text = request.args["text"];
    
    // Check if pattern is risky
    if (_is_risky_regex(pattern)) {
        throw std::invalid_argument("Risky regex pattern");
    }
    
    try {
        std::regex cp(pattern);
        return std::regex_search(text, cp);
    } catch (const std::regex_error& e) {
        throw std::invalid_argument("Invalid regex pattern");
    }
}

// Helper for tests
void assert_raises(std::function<void()> func, bool expect_exception) {
    try {
        func();
        if (expect_exception) {
            std::cerr << "FAIL: Expected exception but none was thrown." << std::endl;
            std::exit(1);
        }
    } catch (const std::exception& e) {
        if (!expect_exception) {
            std::cerr << "FAIL: Unexpected exception: " << e.what() << std::endl;
            std::exit(1);
        }
    }
}

int main() {
    // Test 1: Valid match
    request.args = {{"pattern", "ab+c"}, {"text", "xxabbbcxx"}};
    if (direct() != true) {
        std::cerr << "FAIL: Test 1 expected true" << std::endl;
        return 1;
    }

    // Test 2: Valid no match
    request.args = {{"pattern", "ab+c"}, {"text", "xxacxx"}};
    if (direct() != false) {
        std::cerr << "FAIL: Test 2 expected false" << std::endl;
        return 1;
    }

    // Test 3: Invalid regex should raise
    request.args = {{"pattern", "(["}, {"text", "x"}};
    assert_raises([]() { direct(); }, true);

    // Test 4: Risky regex should raise
    request.args = {{"pattern", "(a+)+$"}, {"text", "aaaaaaaaaa"}};
    assert_raises([]() { direct(); }, true);

    // Test 5: Missing key
    request.args = {{"text", "x"}};
    assert_raises([]() { direct(); }, true);

    // Test 6: Wrong types (In C++ with map<string, string>, types are always string.
    // However, the Python test checks for TypeError if pattern is int.
    // Since we are using a map of strings, we cannot simulate an int in the map 
    // without changing the struct definition or using variants.
    // Given the constraints and the translation provided, this specific TypeError 
    // check for non-string input is not applicable to the C++ map<string, string> implementation.
    // We skip this specific check as it requires a dynamic type system not present in the C++ struct.
    
    std::cout << "All tests passed." << std::endl;
    return 0;
}