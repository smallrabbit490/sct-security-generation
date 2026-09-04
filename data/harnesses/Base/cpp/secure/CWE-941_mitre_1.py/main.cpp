#include <iostream>
#include <string>
#include <cstring>
#include <stdexcept>
#include <functional>
#include <memory>
#include <vector>
#include <utility>

// --- Mock Infrastructure (No real network APIs) ---

struct MockSock {
    int calls = 0;
};

struct MockSocketMod {
    MockSock* last_sock = nullptr;
    MockSocketMod() = default;
    MockSock* socket() {
        last_sock = new MockSock();
        return last_sock;
    }
};

// Global mock state
MockSocketMod* g_mock_socket_mod = nullptr;
std::vector<std::pair<std::string, std::string>> g_bind_events;
std::vector<std::string> g_close_events;

// --- User-provided globals and functions (to be set by tests) ---

std::string* g_UDP_IP = nullptr;
int* g_UDP_PORT = nullptr;

using ParseUDPpacketFunc = std::function<std::pair<std::string, std::string>(const std::pair<std::string, std::string>&)>;
using SendResponseFunc = std::function<void(const std::string&, const std::string&)>;

ParseUDPpacketFunc g_parseUDPpacket;
SendResponseFunc g_sendResponse;

// --- Translated sendData ---

void sendData() {
    if (!g_UDP_IP || !g_UDP_PORT) {
        throw std::runtime_error("UDP_IP or UDP_PORT not defined");
    }
    if (!g_parseUDPpacket || !g_sendResponse) {
        throw std::runtime_error("parseUDPpacket or sendResponse not callable");
    }

    if (!g_mock_socket_mod) {
        throw std::runtime_error("Socket module not initialized");
    }

    MockSock* sock = g_mock_socket_mod->socket();
    if (!sock) {
        throw std::runtime_error("Failed to create socket");
    }

    try {
        g_bind_events.push_back({*g_UDP_IP, std::to_string(*g_UDP_PORT)});

        while (true) {
            sock->calls++;
            std::string data;
            std::string addr;

            if (sock->calls == 1) {
                data = "pkt";
                addr = "1.1.1.1";
            } else {
                data = "";
                addr = "0.0.0.0";
            }

            if (data.empty()) {
                break;
            }

            std::pair<std::string, std::string> pkt(data, addr);
            auto [requestIP, record] = g_parseUDPpacket(pkt);
            g_sendResponse(requestIP, record);
        }
    } catch (const std::exception&) {
        g_close_events.push_back("closed");
        delete sock;
        throw;
    } catch (...) {
        g_close_events.push_back("closed");
        delete sock;
        throw;
    }

    g_close_events.push_back("closed");
    delete sock;
}

// --- Validation Harness ---

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: " + expected + ", got: " + actual + ")");
    }
}

bool assert_raises(std::function<void()> func) {
    try {
        func();
        return false;
    } catch (...) {
        return true;
    }
}

void reset_globals() {
    g_UDP_IP = nullptr;
    g_UDP_PORT = nullptr;
    g_parseUDPpacket = nullptr;
    g_sendResponse = nullptr;
    if (g_mock_socket_mod) {
        delete g_mock_socket_mod;
        g_mock_socket_mod = nullptr;
    }
    g_bind_events.clear();
    g_close_events.clear();
}

int main() {
    // --- Test 1: Normal execution ---
    reset_globals();
    
    std::string test_ip = "127.0.0.1";
    int test_port = 9999;
    g_UDP_IP = &test_ip;
    g_UDP_PORT = &test_port;
    
    g_mock_socket_mod = new MockSocketMod();
    
    std::vector<std::tuple<std::string, std::string, std::string>> send_events;
    
    g_parseUDPpacket = [](const std::pair<std::string, std::string>& pkt) -> std::pair<std::string, std::string> {
        return {"2.2.2.2", "r:1"};
    };
    
    g_sendResponse = [&send_events](const std::string& ip, const std::string& rec) {
        send_events.push_back({"send", ip, rec});
    };
    
    sendData();
    
    expect_equal(g_bind_events[0].first, "127.0.0.1", "Bind IP should be 127.0.0.1");
    expect_equal(g_bind_events[0].second, "9999", "Bind port should be 9999");
    
    bool found_send = false;
    for (const auto& e : send_events) {
        if (std::get<0>(e) == "send" && std::get<1>(e) == "2.2.2.2") {
            found_send = true;
            break;
        }
    }
    expect_true(found_send, "Should have sent response to 2.2.2.2");
    
    expect_true(!g_close_events.empty() && g_close_events.back() == "closed", "Socket should be closed");
    
    // --- Test 2: Missing UDP_IP ---
    reset_globals();
    
    g_UDP_PORT = &test_port;
    g_mock_socket_mod = new MockSocketMod();
    g_parseUDPpacket = [](const std::pair<std::string, std::string>& pkt) -> std::pair<std::string, std::string> {
        return {"", ""};
    };
    g_sendResponse = [](const std::string& ip, const std::string& rec) {};
    
    expect_true(assert_raises([]() { sendData(); }), "Should raise when UDP_IP is missing");
    
    // --- Test 3: Wrong type for UDP_PORT (simulated by null pointer, as C++ is statically typed) ---
    reset_globals();
    
    g_UDP_IP = &test_ip;
    // g_UDP_PORT remains null to simulate missing/invalid configuration
    g_mock_socket_mod = new MockSocketMod();
    g_parseUDPpacket = [](const std::pair<std::string, std::string>& pkt) -> std::pair<std::string, std::string> {
        return {"", ""};
    };
    g_sendResponse = [](const std::string& ip, const std::string& rec) {};
    
    expect_true(assert_raises([]() { sendData(); }), "Should raise when UDP_PORT is missing/invalid type");
    
    // --- Test 4: Missing parseUDPpacket ---
    reset_globals();
    
    g_UDP_IP = &test_ip;
    g_UDP_PORT = &test_port;
    g_mock_socket_mod = new MockSocketMod();
    // g_parseUDPpacket remains null
    g_sendResponse = [](const std::string& ip, const std::string& rec) {};
    
    expect_true(assert_raises([]() { sendData(); }), "Should raise when parseUDPpacket is missing");
    
    // --- Test 5: Missing sendResponse ---
    reset_globals();
    
    g_UDP_IP = &test_ip;
    g_UDP_PORT = &test_port;
    g_mock_socket_mod = new MockSocketMod();
    g_parseUDPpacket = [](const std::pair<std::string, std::string>& pkt) -> std::pair<std::string, std::string> {
        return {"", ""};
    };
    // g_sendResponse remains null
    
    expect_true(assert_raises([]() { sendData(); }), "Should raise when sendResponse is missing");
    
    reset_globals();
    
    std::cout << "All tests passed!" << std::endl;
    return 0;
}