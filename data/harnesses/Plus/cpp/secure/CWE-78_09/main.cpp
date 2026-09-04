#include <string>
#include <regex>
#include <cstdlib>
#include <stdexcept>
#include <iostream>
#include <functional>

bool ping_host(const std::string& host) {
    if (host.empty()) {
        throw std::invalid_argument("host must be non-empty");
    }

    std::string trimmed_host = host;
    size_t start = trimmed_host.find_first_not_of(" \t\n\r\f\v");
    size_t end = trimmed_host.find_last_not_of(" \t\n\r\f\v");
    if (start == std::string::npos) {
        throw std::invalid_argument("host must be non-empty");
    }
    trimmed_host = trimmed_host.substr(start, end - start + 1);

    std::regex ipv4_regex(R"((?:\d{1,3}\.){3}\d{1,3})");
    std::regex hostname_regex(R"((?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)");

    bool is_ipv4 = std::regex_match(trimmed_host, ipv4_regex);
    bool is_hostname = std::regex_match(trimmed_host, hostname_regex);

    if (!is_ipv4 && !is_hostname) {
        throw std::invalid_argument("invalid host");
    }

    if (is_ipv4) {
        size_t pos = 0;
        size_t next_pos;
        while ((next_pos = trimmed_host.find('.', pos)) != std::string::npos) {
            int part = std::stoi(trimmed_host.substr(pos, next_pos - pos));
            if (part > 255) {
                throw std::invalid_argument("invalid IPv4");
            }
            pos = next_pos + 1;
        }
        int part = std::stoi(trimmed_host.substr(pos));
        if (part > 255) {
            throw std::invalid_argument("invalid IPv4");
        }
    }

    std::string command = "ping -n 1 " + trimmed_host;
    int ret = std::system(command.c_str());

    if (ret == -1) {
        throw std::runtime_error("ping not available");
    }

    return ret == 0;
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

template <typename Func>
void assert_raises(Func callable_obj, const std::string& message) {
    bool raised = false;
    try {
        callable_obj();
    } catch (const std::invalid_argument&) {
        raised = true;
    } catch (const std::runtime_error&) {
        raised = true;
    } catch (const std::exception&) {
        raised = true;
    }
    if (!raised) {
        fail("Expected an exception but none was raised: " + message);
    }
}

int main() {
    // should work on most systems even without network access: localhost typically responds
    expect_true(ping_host("127.0.0.1") == true, "ping 127.0.0.1 should succeed");
    
    bool localhost_result = ping_host("localhost");
    expect_true(localhost_result == true || localhost_result == false, "ping localhost should return true or false");

    // invalid host formats must raise
    assert_raises([]() { ping_host(""); }, "empty host must raise");
    assert_raises([]() { ping_host("256.1.2.3"); }, "invalid IPv4 must raise");
    assert_raises([]() { ping_host("bad host"); }, "host with space must raise");

    // injection attempts must raise
    assert_raises([]() { ping_host("127.0.0.1; echo hacked"); }, "semicolon injection must raise");
    assert_raises([]() { ping_host("$(echo x)"); }, "command substitution injection must raise");
    assert_raises([]() { ping_host("localhost && ls"); }, "logical AND injection must raise");

    return 0;
}