#include <iostream>
#include <string>
#include <map>
#include <functional>
#include <stdexcept>

// Mocking the behavior of the Python ldap module and Flask request
// Since we cannot use third-party libraries, we simulate the insecure behavior.

std::map<std::string, std::string> request_args;

std::string normal() {
    // Get the Domain Component (dc) and username from the request
    if (request_args.find("dc") == request_args.end() || request_args.find("username") == request_args.end()) {
        throw std::runtime_error("Missing request arguments");
    }
    std::string unsafe_dc = request_args["dc"];
    std::string unsafe_filter = request_args["username"];

    // Create an LDAP query with them
    std::string dn = "dc=" + unsafe_dc;
    std::string search_filter = "(user=" + unsafe_filter + ")";

    // Establish an LDAP connection on localhost (simulated)
    // In a real scenario, this would involve actual LDAP library calls
    std::string ldap_connection = "ldap://127.0.0.1";
    (void)ldap_connection;

    // Search for the user in the LDAP and return it (simulated)
    // Since we can't actually perform an LDAP search without a library,
    // we return a string representation of what would be returned.
    std::string user = "Search result for dn: " + dn + ", filter: " + search_filter;

    return user;
}

// Helper functions for validation
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

bool string_contains(const std::string& haystack, const std::string& needle) {
    return haystack.find(needle) != std::string::npos;
}

bool raises_exception(std::function<void()> func) {
    try {
        func();
        return false;
    } catch (...) {
        return true;
    }
}

int main() {
    // Test 1: Normal request with valid inputs
    request_args["dc"] = "example";
    request_args["username"] = "alice";
    std::string out = normal();
    expect_true(string_contains(out, "dc=example"), "Test 1 failed: dn not correctly formed");
    expect_true(string_contains(out, "(user=alice)"), "Test 1 failed: filter not correctly formed");

    // Test 2: Normal request with different valid inputs
    request_args["dc"] = "example";
    request_args["username"] = "bob";
    out = normal();
    expect_true(string_contains(out, "dc=example"), "Test 2 failed: dn not correctly formed");
    expect_true(string_contains(out, "(user=bob)"), "Test 2 failed: filter not correctly formed");

    // Test 3: Injection attempt in dc parameter
    // The insecure code blindly concatenates the input, so it should NOT raise an exception.
    // If the code were secure, it would validate/sanitize and raise an error.
    request_args["dc"] = "ex*";
    request_args["username"] = "alice";
    bool raised = raises_exception(normal);
    // For the insecure code, we expect NO exception (raised == false)
    expect_true(!raised, "Test 3 failed: insecure code should not raise exception on malicious dc input");

    // Test 4: Injection attempt in username parameter
    // The insecure code blindly concatenates the input, so it should NOT raise an exception.
    // If the code were secure, it would validate/sanitize and raise an error.
    request_args["dc"] = "example";
    request_args["username"] = "*) (user=admin";
    raised = raises_exception(normal);
    // For the insecure code, we expect NO exception (raised == false)
    expect_true(!raised, "Test 4 failed: insecure code should not raise exception on malicious username input");

    // Test 5: Verify the injection payload is actually present in the output (proving the vulnerability)
    request_args["dc"] = "example";
    request_args["username"] = "*) (user=admin";
    out = normal();
    expect_true(string_contains(out, "(user=*) (user=admin)"), "Test 5 failed: injection payload not reflected in output");

    return 0;
}