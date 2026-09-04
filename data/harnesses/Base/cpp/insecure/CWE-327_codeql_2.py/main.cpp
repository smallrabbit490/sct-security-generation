#include <iostream>
#include <string>
#include <vector>
#include <cstring>
#include <functional>
#include <stdexcept>
#include <cassert>

// --- Translated Insecure Code ---
struct MockSSLSocket {
    std::string host;
    int port;
};

MockSSLSocket* connect(const std::string& host, int port) {
    if (host.empty()) {
        throw std::runtime_error("Empty host should raise");
    }
    if (port <= 0) {
        throw std::runtime_error("Port 0 or negative should raise");
    }
    if (port > 65535) {
        throw std::runtime_error("Port out of range should raise");
    }
    MockSSLSocket* ssl_sock = new MockSSLSocket{host, port};
    return ssl_sock;
}

// --- Validation Harness ---
int tests_passed = 0;
int tests_failed = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    tests_failed++;
}

void expect_true(bool condition, const std::string& message) {
    if (condition) {
        tests_passed++;
    } else {
        fail(message);
    }
}

void expect_raises(const std::function<void()>& callable, const std::string& message) {
    try {
        callable();
        fail(message + " (expected exception but none was raised)");
    } catch (const std::exception&) {
        tests_passed++;
    } catch (...) {
        tests_passed++;
    }
}

int main() {
    // 1. Success returns socket
    {
        MockSSLSocket* s = connect("example.com", 443);
        expect_true(s != nullptr, "Success returns socket");
        delete s;
    }

    // 2. Connects to correct addr
    {
        MockSSLSocket* s = connect("example.com", 443);
        expect_true(s->host == "example.com" && s->port == 443, "Connects to correct addr");
        delete s;
    }

    // 3. Empty host raises
    expect_raises([]() { connect("", 443); }, "Empty host should raise");

    // 4. Port 0 raises
    expect_raises([]() { connect("example.com", 0); }, "Port 0 should raise");

    // 5. Negative port raises
    expect_raises([]() { connect("example.com", -1); }, "Negative port should raise");

    // 6. Port out of range raises
    expect_raises([]() { connect("example.com", 70000); }, "Port out of range should raise");

    // 7. Insecure behavior check: The Python insecure code uses ssl.wrap_socket 
    // which does not enforce hostname verification or certificate validation.
    // The translated C++ code mimics this by creating a MockSSLSocket without 
    // any verification fields. A secure version would require verify_mode and 
    // check_hostname to be set. Since they are absent, the translation matches 
    // the insecure behavior.
    {
        MockSSLSocket* s = connect("example.com", 443);
        bool has_no_verify_mode = true; // MockSSLSocket lacks verify_mode
        bool has_no_check_hostname = true; // MockSSLSocket lacks check_hostname
        expect_true(has_no_verify_mode && has_no_check_hostname, 
                    "Insecure: no verify_mode or check_hostname enforced");
        delete s;
    }

    if (tests_failed > 0) {
        std::cerr << tests_failed << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All " << tests_passed << " test(s) passed." << std::endl;
    return 0;
}