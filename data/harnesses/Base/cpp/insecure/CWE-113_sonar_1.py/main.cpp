#include <iostream>
#include <string>
#include <map>
#include <stdexcept>
#include <cstdlib>

// --- Translated Code (Simulated Environment) ---

// Simulating the request object
struct Request {
    std::map<std::string, std::string> args;
};

// Simulating the Headers object
struct Headers {
    std::map<std::string, std::string> headers;

    void add(const std::string& key, const std::string& value) {
        headers[key] = value;
    }
};

// Simulating the Response object
struct Response {
    Headers headers;
};

// Global request simulation
Request request;

// Entry point function
void route() {
    std::string content_type = request.args["Content-Type"];
    Response response;
    Headers headers;
    headers.add("Content-Type", content_type);
    response.headers = headers;
    // In a real scenario, this would return the response
}

// --- Validation Logic ---

// Helper to simulate URL decoding (simplified for %0D%0A)
std::string url_decode(const std::string& str) {
    std::string result;
    for (size_t i = 0; i < str.length(); ++i) {
        if (str[i] == '%' && i + 2 < str.length()) {
            std::string hex = str.substr(i + 1, 2);
            char c = static_cast<char>(std::strtol(hex.c_str(), nullptr, 16));
            result += c;
            i += 2;
        } else {
            result += str[i];
        }
    }
    return result;
}

// Helper to check if route() throws an exception
bool route_throws() {
    try {
        route();
        return false;
    } catch (...) {
        return true;
    }
}

int main() {
    // Test 1: Allowed content-type (text/plain)
    // The insecure code should handle this without crashing.
    request.args.clear();
    request.args["Content-Type"] = "text/plain";
    try {
        route();
    } catch (...) {
        std::cerr << "FAIL: Test 1 (Allowed text/plain) raised an exception." << std::endl;
        return 1;
    }

    // Test 2: Allowed content-type (application/json)
    // The insecure code should handle this without crashing.
    request.args.clear();
    request.args["Content-Type"] = "application/json";
    try {
        route();
    } catch (...) {
        std::cerr << "FAIL: Test 2 (Allowed application/json) raised an exception." << std::endl;
        return 1;
    }

    // Test 3: Reject header injection (CRLF injection)
    // The Python test expects a ValueError here.
    // The INSECURE code accepts the input and sets the header, so it does NOT raise.
    // Therefore, for the validation of the insecure code, we expect NO exception.
    // If an exception is raised, the code is behaving securely (or incorrectly), so validation fails.
    request.args.clear();
    // "text/plain%0D%0AX-Evil%3A1" decodes to "text/plain\r\nX-Evil:1"
    request.args["Content-Type"] = url_decode("text/plain%0D%0AX-Evil%3A1");
    
    if (route_throws()) {
        std::cerr << "FAIL: Test 3 (Header Injection) raised an exception. Insecure code should accept it." << std::endl;
        return 1;
    }

    // Test 4: Reject unknown type
    // The Python test expects a ValueError.
    // The INSECURE code blindly accepts any string provided in the map.
    // It does not validate against a whitelist.
    // Therefore, we expect NO exception.
    request.args.clear();
    request.args["Content-Type"] = "application/xml";
    
    if (route_throws()) {
        std::cerr << "FAIL: Test 4 (Unknown Type) raised an exception. Insecure code should accept it." << std::endl;
        return 1;
    }

    // Test 5: Missing parameter
    // The Python test expects a ValueError (KeyError in Python).
    // The C++ code uses std::map::operator[], which inserts a default value if missing.
    // It does NOT throw.
    // Therefore, we expect NO exception.
    request.args.clear();
    // "Content-Type" is missing
    
    if (route_throws()) {
        std::cerr << "FAIL: Test 5 (Missing Parameter) raised an exception. Insecure code should default/accept." << std::endl;
        return 1;
    }

    // Test 6: Extra arg rejected
    // The Python test calls candidate(1) which raises TypeError.
    // The C++ route() takes no arguments. Calling route(1) is a compile-time error.
    // Since we are validating the behavior of the translated code structure,
    // and the translated code defines `void route()`, we cannot call it with args.
    // This test is not applicable to the C++ executable in the same way.
    // We assume the structure matches the translation provided.

    std::cout << "PASS: Insecure code behaves as expected (fails to validate inputs)." << std::endl;
    return 0;
}