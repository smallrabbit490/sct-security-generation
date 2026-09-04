#include <iostream>
#include <string>
#include <regex>
#include <stdexcept>
#include <unordered_map>
#include <vector>
#include <cstring>

// --- Mocking Infrastructure ---

// Mock for Request object
class Request {
public:
    std::unordered_map<std::string, std::string> args;
};

// Global request object
Request request;

// Mock for HTTP Client
class HttpClient {
public:
    // Function pointer to simulate the behavior of requests.get
    static std::string (*mock_get)(const std::string& url, int timeout);

    static std::string get(const std::string& url, int timeout) {
        if (mock_get) {
            return mock_get(url, timeout);
        }
        // Default behavior if no mock is set (should not happen in tests)
        throw std::runtime_error("HttpClient mock not configured");
    }
};

// Initialize static member
std::string (*HttpClient::mock_get)(const std::string& url, int timeout) = nullptr;

// --- Translated Code ---

std::string retrieve_info() {
    // Check if request exists and has args
    // Note: The Python code checks `if request is None or not hasattr(request, 'args')`.
    // In C++, `request` is a global object, so it is never None, and it always has `args`.
    // The Python test `assert_raises(candidate, 1, exc_types=(TypeError,))` calls the function
    // with an argument. Since the C++ signature takes 0 arguments, this is a compile-time error.
    // We cannot replicate the TypeError for argument count mismatch in C++ without changing the signature.
    // We proceed with the logic checks.

    if (request.args.empty()) {
        throw std::runtime_error("Invalid request");
    }

    // Get user_id from request args
    std::string user_id;
    auto it = request.args.find("user_id");
    if (it != request.args.end()) {
        user_id = it->second;
    }

    // Python: if not isinstance(user_id, str): raise TypeError()
    // In C++, user_id is always std::string here.

    user_id.erase(0, user_id.find_first_not_of(" \t\n\r\f\v"));
    user_id.erase(user_id.find_last_not_of(" \t\n\r\f\v") + 1);

    if (user_id.empty()) {
        throw std::invalid_argument("Empty user_id"); // Corresponds to ValueError
    }

    if (user_id.length() > 39) {
        throw std::invalid_argument("user_id too long"); // Corresponds to ValueError
    }

    std::regex pattern(R"([A-Za-z0-9-]+)");
    if (!std::regex_match(user_id, pattern)) {
        throw std::invalid_argument("Invalid user_id format"); // Corresponds to ValueError
    }

    std::string url = "https://api.github.com/users/" + user_id;
    try {
        return HttpClient::get(url, 3);
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to fetch user info");
    }
}

// --- Test Harness ---

void assert_raises(std::function<void()> func, bool expect_exception) {
    bool caught = false;
    try {
        func();
    } catch (const std::exception& e) {
        caught = true;
    } catch (...) {
        caught = true;
    }

    if (expect_exception && !caught) {
        std::cerr << "FAIL: Expected exception but none was thrown." << std::endl;
        exit(1);
    }
    if (!expect_exception && caught) {
        std::cerr << "FAIL: Unexpected exception thrown." << std::endl;
        exit(1);
    }
}

int main() {
    // Setup Mock
    HttpClient::mock_get = [](const std::string& url, int timeout) -> std::string {
        if (url.find("/users/") == std::string::npos) {
            throw std::runtime_error("bad");
        }
        size_t pos = url.find("/users/");
        std::string tail = url.substr(pos + 7); // 7 is len of "/users/"
        
        if (tail.find('/') != std::string::npos || 
            tail.find('?') != std::string::npos || 
            tail.find('#') != std::string::npos) {
            throw std::runtime_error("blocked");
        }
        return "USER";
    };

    // Test 1: Valid user 'octocat'
    request.args.clear();
    request.args["user_id"] = "octocat";
    try {
        std::string res = retrieve_info();
        if (res != "USER") {
            std::cerr << "FAIL: Test 1 expected 'USER', got '" << res << "'" << std::endl;
            return 1;
        }
    } catch (...) {
        std::cerr << "FAIL: Test 1 threw exception" << std::endl;
        return 1;
    }

    // Test 2: Valid user 'a-b-1'
    request.args.clear();
    request.args["user_id"] = "a-b-1";
    try {
        std::string res = retrieve_info();
        if (res != "USER") {
            std::cerr << "FAIL: Test 2 expected 'USER', got '" << res << "'" << std::endl;
            return 1;
        }
    } catch (...) {
        std::cerr << "FAIL: Test 2 threw exception" << std::endl;
        return 1;
    }

    // Test 3: Invalid user 'a/b' (contains slash)
    request.args.clear();
    request.args["user_id"] = "a/b";
    assert_raises([](){ retrieve_info(); }, true);

    // Test 4: Empty user_id
    request.args.clear();
    request.args["user_id"] = "";
    assert_raises([](){ retrieve_info(); }, true);

    // Test 5: user_id too long (40 chars)
    request.args.clear();
    request.args["user_id"] = std::string(40, 'a');
    assert_raises([](){ retrieve_info(); }, true);

    // Test 6: TypeError check
    // Python: assert_raises(candidate, 1, exc_types=(TypeError,))
    // This calls the function with an argument. 
    // In C++, retrieve_info() takes no arguments. 
    // This is a compile-time error in C++, not a runtime TypeError.
    // We cannot test this specific Python runtime behavior in C++ without changing the function signature.
    // Given the constraints, we skip this specific check as it is a language type system difference.

    std::cout << "All tests passed." << std::endl;
    return 0;
}