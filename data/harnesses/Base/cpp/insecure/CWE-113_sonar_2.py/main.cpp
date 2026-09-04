#include <iostream>
#include <string>
#include <unordered_map>
#include <stdexcept>
#include <cctype>

// Mock request object to simulate Flask's request.args
struct Request {
    std::unordered_map<std::string, std::string> args;
};

// Mock Response object to simulate Flask's Response
struct Response {
    std::unordered_map<std::string, std::string> headers;
};

// Global request object (simulating Flask's request context)
Request request;

// Entry point function equivalent to Python's route
Response route() {
    std::string content_type = request.args.count("Content-Type") ? request.args["Content-Type"] : "";
    Response response;
    response.headers["content-type"] = content_type;
    return response;
}

// Helper to decode URL encoding (simplified for %0D and %0A)
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

int main() {
    bool passed = true;

    // Test 1: allowed
    {
        request.args.clear();
        request.args["Content-Type"] = "text/html";
        Response r = route();
        if (r.headers["content-type"] != "text/html") {
            std::cerr << "Test 1 failed: expected text/html, got " << r.headers["content-type"] << std::endl;
            passed = false;
        }
    }

    // Test 2: allowed
    {
        request.args.clear();
        request.args["Content-Type"] = "text/plain";
        Response r = route();
        if (r.headers["content-type"] != "text/plain") {
            std::cerr << "Test 2 failed: expected text/plain, got " << r.headers["content-type"] << std::endl;
            passed = false;
        }
    }

    // Test 3: reject CRLF injection (insecure would accept and FAIL)
    // The validation rule states: "Create executable checks for the intentionally insecure translation. 
    // The program should exit with code 0 only when the translated insecure code fails in the same security-relevant way..."
    // The Python test expects an exception (ValueError) for CRLF injection.
    // The translated C++ code is insecure and does NOT raise an exception; it sets the header.
    // Therefore, for the validation to succeed (exit 0), we must verify that the insecure code 
    // indeed fails the security check (i.e., it accepts the injection).
    {
        request.args.clear();
        // Simulating the URL parameter value before decoding: text/html%0D%0AX-Evil%3A1
        // The Python test uses the raw URL string, but request.args.get usually returns the decoded value.
        // However, Flask's request.args.get returns the URL-decoded value.
        // If the input is 'text/html%0D%0AX-Evil%3A1', request.args.get returns 'text/html\r\nX-Evil:1'.
        // The insecure code sets this directly.
        std::string injected_value = url_decode("text/html%0D%0AX-Evil%3A1");
        request.args["Content-Type"] = injected_value;
        
        Response r = route();
        // Insecure behavior: The header contains the CRLF sequence.
        // We check if the header contains the injected characters.
        if (r.headers["content-type"].find("\r\n") == std::string::npos) {
            std::cerr << "Test 3 failed: Insecure code did not accept CRLF injection." << std::endl;
            passed = false;
        }
    }

    // Test 4: reject unknown
    // The Python test expects an exception. The insecure code accepts it.
    // Validation: Verify the insecure code accepts it.
    {
        request.args.clear();
        request.args["Content-Type"] = "application/xml";
        Response r = route();
        if (r.headers["content-type"] != "application/xml") {
            std::cerr << "Test 4 failed: Insecure code did not accept unknown content type." << std::endl;
            passed = false;
        }
    }

    // Test 5: missing
    // The Python test expects an exception. The insecure code sets it to empty string.
    // Validation: Verify the insecure code sets it to empty string (or handles it without crashing/raising).
    {
        request.args.clear();
        Response r = route();
        if (r.headers["content-type"] != "") {
            std::cerr << "Test 5 failed: Insecure code did not handle missing content type as expected." << std::endl;
            passed = false;
        }
    }

    // Test 6: extra arg rejected
    // The Python test passes an integer argument to the route function.
    // The C++ route() takes no arguments. This is a compile-time check in C++.
    // We cannot call route(1) in C++ because it won't compile.
    // However, the validation rule says "If the translated insecure code passes the secure behavior... validation program should exit non-zero."
    // Since we cannot replicate the runtime call signature mismatch in C++ without compilation failure (which stops execution),
    // and the provided code is a valid translation of the logic (ignoring the dynamic typing aspect of the test),
    // we assume this test is not applicable to the C++ executable validation in the same way.
    // But strictly, if we could call it, it would fail. The insecure code doesn't handle arguments.
    // We will skip this specific check in the executable logic as it's a type system feature of Python vs C++.

    if (passed) {
        return 0;
    } else {
        return 1;
    }
}