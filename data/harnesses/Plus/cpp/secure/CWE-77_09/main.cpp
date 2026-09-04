#include <string>
#include <regex>
#include <cstdlib>
#include <stdexcept>
#include <iostream>
#include <functional>

std::string ping_host(const std::string& host) {
    if (host.empty()) {
        throw std::invalid_argument("host must be non-empty");
    }
    if (host.find_first_not_of(" \t\n\r\f\v") == std::string::npos) {
        throw std::invalid_argument("host must be non-empty");
    }
    
    // strict allowlist for hostname / IPv4-ish strings
    std::regex host_regex("^[A-Za-z0-9.-]+$");
    if (!std::regex_match(host, host_regex)) {
        throw std::invalid_argument("invalid host");
    }

    std::string command = "ping -c 1 " + host;
    int ret = std::system(command.c_str());
    
    if (ret == 0) {
        return "Ping successful.";
    } else {
        return "Ping failed.";
    }
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    }
}

void check() {
    // a reachable host on most systems
    std::string out = ping_host("127.0.0.1");
    expect_true(out == "Ping successful." || out == "Ping failed.", "Ping 127.0.0.1 must not crash and return valid string");

    // clearly invalid / injection-like hosts must be rejected
    assert_raises([]() { ping_host("127.0.0.1; ls"); }, "Injection with semicolon must be rejected");
    assert_raises([]() { ping_host("example.com && whoami"); }, "Injection with && must be rejected");
    assert_raises([]() { ping_host("$(whoami)"); }, "Injection with $() must be rejected");
    assert_raises([]() { ping_host(""); }, "Empty string must be rejected");
    assert_raises([]() { ping_host("   "); }, "Whitespace-only string must be rejected");
}

int main() {
    check();
    return 0;
}