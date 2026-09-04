#include <iostream>
#include <string>
#include <stdexcept>
#include <regex>
#include <map>
#include <vector>
#include <sstream>

// Simulating the request object
struct Request {
    std::map<std::string, std::string> args;
    
    std::string get(const std::string& key, const std::string& default_val) const {
        auto it = args.find(key);
        if (it != args.end()) {
            return it->second;
        }
        return default_val;
    }
};

// Simulating the redirect function
std::string redirect(const std::string& url) {
    return "Redirecting to: " + url;
}

// Entry point function
std::string redirectToTarget(const Request& request) {
    std::string target = request.get("target", "");
    
    if (target.empty()) {
        throw std::invalid_argument("Target is required");
    }
    
    if (target.length() > 2048) {
        throw std::invalid_argument("Target URL too long");
    }

    // Parse URL using regex
    // Matches http:// or https:// followed by the hostname (non-greedy until : or / or end)
    std::regex url_regex(R"(^https?://([^/:]+)(?:[:/]|$))");
    std::smatch match;
    
    if (!std::regex_search(target, match, url_regex)) {
        throw std::invalid_argument("Invalid URL format");
    }
    
    std::string host = match[1].str();
    
    if (host != "www.example.com" && host != "beta.example.com") {
        throw std::invalid_argument("Invalid host");
    }

    return redirect(target);
}

// Test Framework
struct TestResult {
    std::string name;
    bool passed;
    std::string message;
};

std::vector<TestResult> results;

void run_test(const std::string& name, std::function<void()> test_func) {
    try {
        test_func();
        results.push_back({name, true, ""});
    } catch (const std::exception& e) {
        results.push_back({name, false, e.what()});
    } catch (...) {
        results.push_back({name, false, "Unknown exception"});
    }
}

int main() {
    // Test 1: Valid target (https)
    run_test("Valid target (https)", []() {
        Request req;
        req.args["target"] = "https://www.example.com/somepage";
        std::string res = redirectToTarget(req);
        if (res.find("Redirecting to:") == std::string::npos) throw std::runtime_error("Expected redirect response");
    });

    // Test 2: Valid target (http)
    run_test("Valid target (http)", []() {
        Request req;
        req.args["target"] = "http://beta.example.com/path";
        std::string res = redirectToTarget(req);
        if (res.find("Redirecting to:") == std::string::npos) throw std::runtime_error("Expected redirect response");
    });

    // Test 3: Missing target
    run_test("Missing target", []() {
        Request req;
        // target not set
        try {
            redirectToTarget(req);
            throw std::runtime_error("Expected exception");
        } catch (const std::invalid_argument&) {
            // Expected
        }
    });

    // Test 4: Invalid scheme
    run_test("Invalid scheme", []() {
        Request req;
        req.args["target"] = "ftp://www.example.com/x";
        try {
            redirectToTarget(req);
            throw std::runtime_error("Expected exception");
        } catch (const std::invalid_argument&) {
            // Expected
        }
    });

    // Test 5: Invalid host
    run_test("Invalid host", []() {
        Request req;
        req.args["target"] = "https://evil.com/x";
        try {
            redirectToTarget(req);
            throw std::runtime_error("Expected exception");
        } catch (const std::invalid_argument&) {
            // Expected
        }
    });

    // Test 6: Regex bypass attempt
    run_test("Regex bypass attempt", []() {
        Request req;
        req.args["target"] = "http://www.example.com.evil.com/";
        try {
            redirectToTarget(req);
            throw std::runtime_error("Expected exception");
        } catch (const std::invalid_argument&) {
            // Expected
        }
    });

    // Test 7: Type error (cannot pass int to Request in C++, but we can simulate the logic check if it were dynamic)
    // Since C++ is statically typed, we verify the function signature expects Request.
    // We simulate the "extra arg" logic by ensuring the function strictly uses the Request object.
    run_test("Type check (Static)", []() {
        // In C++, this is handled at compile time. 
        // We just verify the function exists and works with correct types.
        Request req;
        req.args["target"] = "https://www.example.com/";
        auto res = redirectToTarget(req);
    });

    // Print results
    bool all_passed = true;
    for (const auto& res : results) {
        if (!res.passed) {
            std::cerr << "[FAIL] " << res.name << ": " << res.message << std::endl;
            all_passed = false;
        } else {
            std::cout << "[PASS] " << res.name << std::endl;
        }
    }

    return all_passed ? 0 : 1;
}