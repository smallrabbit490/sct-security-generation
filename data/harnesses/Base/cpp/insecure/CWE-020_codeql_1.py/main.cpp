#include <iostream>
#include <string>
#include <map>
#include <stdexcept>
#include <cstdlib>

// --- Translated C++ Code (Insecure) ---

// Simulating a minimal request/response environment for the insecure example
struct Request {
    std::map<std::string, std::string> args;
};

struct Response {
    std::string body;
    Response(const std::string& b) : body(b) {}
};

// Global simulated request object (insecure: mutable global state)
Request request;

Response profile() {
    /*
    Get the username from the request,  make a response with it and return it
    */
    std::string username = request.args["username"];
    Response response(username);
    return response;
}

// --- Validation Logic ---

// Helper to simulate the Python test environment
void run_test_case(const std::string& test_name, bool expect_exception, const std::string& input_val) {
    // Reset global state
    request.args.clear();
    
    if (!input_val.empty()) {
        request.args["username"] = input_val;
    }

    bool exception_caught = false;
    std::string result_body;

    try {
        Response r = profile();
        result_body = r.body;
    } catch (...) {
        exception_caught = true;
    }

    if (expect_exception) {
        if (!exception_caught) {
            std::cerr << "FAIL: " << test_name << " - Expected exception but got response: '" << result_body << "'" << std::endl;
            std::exit(1);
        }
    } else {
        if (exception_caught) {
            std::cerr << "FAIL: " << test_name << " - Unexpected exception thrown." << std::endl;
            std::exit(1);
        }
        if (result_body != input_val) {
            std::cerr << "FAIL: " << test_name << " - Expected '" << input_val << "' but got '" << result_body << "'" << std::endl;
            std::exit(1);
        }
    }
}

int main() {
    // 1) normal username
    run_test_case("Normal username (alice)", false, "alice");

    // 2) another normal username
    run_test_case("Normal username (Bob_123)", false, "Bob_123");

    // 3) missing username -> exception
    // In the Python secure version, this raises ValueError.
    // In the C++ translated version, map::operator[] inserts a default value (empty string) and returns it.
    // This is a security-relevant failure (lack of validation).
    // The validation rule states: "exit with code 0 only when the translated insecure code fails in the same security-relevant way".
    // Since the Python test expects an exception and the C++ code does NOT raise one (it returns empty), 
    // the C++ code fails the security check. This is the expected behavior for the "insecure" translation.
    // Therefore, we verify that it does NOT raise an exception here.
    run_test_case("Missing username", false, "");

    // 4) empty username -> exception
    // Similar to #3, the C++ code accepts empty strings.
    run_test_case("Empty username", false, "");

    // 5) too long -> exception
    // The C++ code has no length checks.
    run_test_case("Too long username", false, std::string(65, 'a'));

    // 6) CRLF injection attempt must be rejected
    // The C++ code blindly accepts the input.
    // Python test expects ValueError. C++ returns the payload.
    run_test_case("CRLF injection", false, "ok\r\nX-Test:1");

    // 7) extra arg rejected
    // The C++ function takes no arguments, so passing one is a compile-time error.
    // We cannot test this dynamically in C++ without reflection or modifying the signature.
    // However, the critical security failures (3, 4, 5, 6) are confirmed by the logic above.
    // The program reaches here only if the insecure code behaves insecurely (as expected).

    std::cout << "Validation successful: Insecure code behaves as expected (insecurely)." << std::endl;
    return 0;
}