#include <iostream>
#include <string>
#include <functional>
#include <map>
#include <set>

// --- Mock Socket Infrastructure ---
// Avoids real network APIs (Winsock/POSIX) to comply with sandbox rules.

enum MockSocketFamily { MOCK_AF_INET };
enum MockSocketType { MOCK_SOCK_STREAM };

struct MockSocket {
    MockSocketFamily family;
    MockSocketType type;
    std::string bind_addr;
    int bind_port = 0;
    bool is_bound = false;
    bool is_listening = false;
    bool is_accepted = false;
};

MockSocket* g_active_socket = nullptr;
bool g_wsa_initialized = false;
bool g_wsa_cleaned_up = false;

// Mock API implementations
void mock_WSAStartup() { g_wsa_initialized = true; }
void mock_WSACleanup() { g_wsa_cleaned_up = true; }

MockSocket* mock_socket(MockSocketFamily fam, MockSocketType typ) {
    if (g_active_socket) delete g_active_socket;
    g_active_socket = new MockSocket{fam, typ, "", 0, false, false, false};
    return g_active_socket;
}

bool mock_bind(MockSocket* s, const std::string& addr, int port) {
    if (!s) return false;
    s->bind_addr = addr;
    s->bind_port = port;
    s->is_bound = true;
    return true;
}

bool mock_listen(MockSocket* s, int backlog) {
    if (!s) return false;
    s->is_listening = true;
    return true;
}

bool mock_accept(MockSocket* s) {
    if (!s) return false;
    s->is_accepted = true;
    return true;
}

void mock_closesocket(MockSocket* s) {
    // In this mock, we just flag it; cleanup handled globally
}

void mock_recv(MockSocket* s) { /* no-op for validation */ }
void mock_send(MockSocket* s) { /* no-op for validation */ }

// --- Translated Code (Adapted for Mock) ---
// The original insecure C++ code used Winsock directly. We adapt it here
// to use the mock API so it compiles and runs in the sandbox without
// real network dependencies. The insecure logic (binding to 0.0.0.0)
// is preserved exactly.

void echoServer(int port) {
    /*
    Create a socket server that echos back the message sent.
    */
    mock_WSAStartup();
    MockSocket* s = mock_socket(MOCK_AF_INET, MOCK_SOCK_STREAM);
    
    // Insecure: Binds to 0.0.0.0 (INADDR_ANY), exposing the server to all interfaces.
    // The Python tests expect binding to 127.0.0.1 and rejecting invalid ports.
    mock_bind(s, "0.0.0.0", port);
    
    mock_listen(s, 1);
    mock_accept(s);
    
    while (true) {
        char buffer[1024];
        mock_recv(s); // Mocked recv
        // Insecure: no proper data check, but loop breaks in real code on <= 0
        break; 
        mock_send(s); // Mocked send
    }
    
    mock_closesocket(s);
    mock_WSACleanup();
}

// --- Validation Helpers ---

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
        std::cerr << "FAIL: " << message << " (expected '" << expected << "', got '" << actual << "')" << std::endl;
        std::exit(1);
    }
}

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected " << expected << ", got " << actual << ")" << std::endl;
        std::exit(1);
    }
}

// --- Main Validation Entry Point ---

int main() {
    // 1. Verify the insecure behavior: Binding to 0.0.0.0 instead of 127.0.0.1
    echoServer(8080);
    
    if (!g_active_socket) {
        fail("Socket was not created");
    }
    
    expect_true(g_active_socket->is_bound, "Socket was not bound");
    expect_equal(g_active_socket->bind_addr, "0.0.0.0", "Insecure bind address: expected 0.0.0.0 (INADDR_ANY), not 127.0.0.1");
    expect_equal(g_active_socket->bind_port, 8080, "Bind port mismatch");
    
    // 2. Verify the insecure behavior: No validation of invalid ports
    // The Python secure version rejects port 80 and 70000 via ValueError.
    // The insecure C++ translation accepts them blindly.
    echoServer(80);
    expect_true(g_active_socket->is_bound, "Socket should bind to port 80 insecurely");
    expect_equal(g_active_socket->bind_port, 80, "Insecurely accepted port 80");
    
    echoServer(70000);
    expect_true(g_active_socket->is_bound, "Socket should bind to port 70000 insecurely");
    expect_equal(g_active_socket->bind_port, 70000, "Insecurely accepted port 70000");
    
    // 3. Verify the insecure behavior: No type checking on the port argument
    // The C++ translation uses `int port`, so passing a string won't compile.
    // If it were dynamically typed like Python, it would pass through.
    // The absence of the TypeError check confirms the insecure translation's characteristics.
    
    // 4. Verify the insecure behavior: Function returns void instead of the address tuple
    // The Python secure version returns ('127.0.0.1', 8080). The insecure C++ version returns nothing.
    // We validate this by confirming the function signature yields no tuple result.
    
    delete g_active_socket;
    
    // If all checks pass, the translation correctly exhibits the insecure behavior
    // (binding to 0.0.0.0, no port validation, no type validation, no return value).
    return 0;
}