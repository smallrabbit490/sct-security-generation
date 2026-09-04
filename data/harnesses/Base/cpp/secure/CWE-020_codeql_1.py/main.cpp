#include <iostream>
#include <string>
#include <stdexcept>
#include <map>
#include <vector>
#include <cctype>

// Simulating the request object with a map of query parameters
struct Request {
    std::map<std::string, std::string> args;
};

// Simulating the response object
struct Response {
    std::string data;
    Response(const std::string& content) : data(content) {}
};

// Entry point function equivalent to the Python profile()
Response profile(const Request& request) {
    // Get the username from the request arguments
    std::string username;
    auto it = request.args.find("username");
    if (it != request.args.end()) {
        username = it->second;
    } else {
        throw std::invalid_argument("Username not provided");
    }

    // Basic validation: prevent empty or overly long usernames
    if (username.empty() || username.length() > 64) {
        throw std::invalid_argument("Invalid username length");
    }

    // Prevent CRLF injection
    for (char c : username) {
        if (c == '\r' || c == '\n') {
            throw std::invalid_argument("Invalid characters in username");
        }
    }

    // Create and return the response
    return Response(username);
}

// Helper to decode URL encoded strings (simplified for test cases)
std::string url_decode(const std::string& str) {
    std::string result;
    for (size_t i = 0; i < str.size(); ++i) {
        if (str[i] == '%' && i + 2 < str.size()) {
            std::string hex = str.substr(i + 1, 2);
            char c = static_cast<char>(std::stoi(hex, nullptr, 16));
            result += c;
            i += 2;
        } else {
            result += str[i];
        }
    }
    return result;
}

// Helper to parse query string into a map
std::map<std::string, std::string> parse_query_string(const std::string& query) {
    std::map<std::string, std::string> args;
    if (query.empty()) return args;

    std::vector<std::string> pairs;
    size_t start = 0;
    size_t end = query.find('&');
    while (end != std::string::npos) {
        pairs.push_back(query.substr(start, end - start));
        start = end + 1;
        end = query.find('&', start);
    }
    pairs.push_back(query.substr(start));

    for (const auto& pair : pairs) {
        size_t eq_pos = pair.find('=');
        if (eq_pos != std::string::npos) {
            std::string key = pair.substr(0, eq_pos);
            std::string value = url_decode(pair.substr(eq_pos + 1));
            args[key] = value;
        }
    }
    return args;
}

// Test harness
int main() {
    int passed = 0;
    int total = 0;

    // Helper macro for tests
    auto run_test = [&](const std::string& name, auto test_func) {
        total++;
        try {
            test_func();
            passed++;
            std::cout << "[PASS] " << name << std::endl;
        } catch (const std::exception& e) {
            std::cout << "[FAIL] " << name << ": " << e.what() << std::endl;
        } catch (...) {
            std::cout << "[FAIL] " << name << ": Unknown exception" << std::endl;
        }
    };

    // 1) normal username
    run_test("normal username", [&]() {
        Request req;
        req.args = parse_query_string("username=alice");
        Response r = profile(req);
        if (r.data != "alice") throw std::runtime_error("Expected 'alice'");
    });

    // 2) another normal username
    run_test("another normal username", [&]() {
        Request req;
        req.args = parse_query_string("username=Bob_123");
        Response r = profile(req);
        if (r.data != "Bob_123") throw std::runtime_error("Expected 'Bob_123'");
    });

    // 3) missing username -> exception
    run_test("missing username", [&]() {
        Request req;
        req.args = parse_query_string("");
        try {
            profile(req);
            throw std::runtime_error("Expected exception");
        } catch (const std::invalid_argument&) {
            // Expected
        }
    });

    // 4) empty username -> exception
    run_test("empty username", [&]() {
        Request req;
        req.args = parse_query_string("username=");
        try {
            profile(req);
            throw std::runtime_error("Expected exception");
        } catch (const std::invalid_argument&) {
            // Expected
        }
    });

    // 5) too long -> exception
    run_test("too long username", [&]() {
        std::string long_name(65, 'a');
        std::string query = "username=" + long_name;
        Request req;
        req.args = parse_query_string(query);
        try {
            profile(req);
            throw std::runtime_error("Expected exception");
        } catch (const std::invalid_argument&) {
            // Expected
        }
    });

    // 6) CRLF injection attempt must be rejected
    run_test("CRLF injection", [&]() {
        // %0D is \r, %0A is \n. Decoded: "ok\r\nX-Test:1"
        Request req;
        req.args = parse_query_string("username=ok%0D%0AX-Test%3A1");
        try {
            profile(req);
            throw std::runtime_error("Expected exception");
        } catch (const std::invalid_argument&) {
            // Expected
        }
    });

    // 7) extra arg rejected (Type mismatch in Python, here we simulate by passing invalid request structure if possible, 
    // but since C++ is statically typed, we can't pass an int to profile. 
    // We verify the function signature matches the expected usage.)
    run_test("signature check", [&]() {
        // This test ensures the function exists and is callable with the correct types.
        // In C++, this is verified at compile time, but we include a runtime check for completeness.
        Request req;
        req.args = parse_query_string("username=test");
        Response r = profile(req);
        if (r.data != "test") throw std::runtime_error("Signature check failed");
    });

    std::cout << "--------------------------------" << std::endl;
    std::cout << "Passed: " << passed << "/" << total << std::endl;

    return (passed == total) ? 0 : 1;
}