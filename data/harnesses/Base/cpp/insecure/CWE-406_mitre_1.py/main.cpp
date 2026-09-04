#include <iostream>
#include <string>
#include <cstring>
#include <vector>
#include <stdexcept>
#include <type_traits>
#include <cstdint>

// Mock headers for Windows compatibility in the validation harness
// The actual translated code uses POSIX headers, but we need to mock them
// to run the validation logic on Windows without linking against Winsock2.
// This allows us to test the logic flow and the specific vulnerability (CWE-406)
// which is about the lack of input validation on the port number.

#ifdef _WIN32
    // Mock types and functions for socket operations
    typedef int socklen_t;
    struct sockaddr {
        unsigned short sa_family;
        char sa_data[14];
    };
    struct sockaddr_in {
        short sin_family;
        unsigned short sin_port;
        struct in_addr {
            unsigned long s_addr;
        } sin_addr;
        char sin_zero[8];
    };
    #define AF_INET 2
    #define SOCK_DGRAM 2
    #define INADDR_ANY ((unsigned long)0)
    
    // Mock functions
    inline int socket(int, int, int) { return 1; }
    inline int bind(int, const struct sockaddr*, int) { return 0; }
    inline unsigned short htons(unsigned short hostshort) { return hostshort; }
    inline unsigned long inet_addr(const char*) { return INADDR_ANY; }
    inline int close(int) { return 0; }
    
    // State for mocking recvfrom
    extern std::vector<std::pair<std::string, std::string>> mock_packets;
    extern size_t mock_packet_index;
    
    inline int recvfrom(int sockfd, char* buffer, size_t len, int flags, struct sockaddr* src_addr, socklen_t* addrlen) {
        if (mock_packet_index >= mock_packets.size()) {
            // Simulate timeout/blocking or end of stream
            return -1;
        }
        
        auto& p = mock_packets[mock_packet_index++];
        if (p.first.size() > len) return -1; // Error if buffer too small
        
        memcpy(buffer, p.first.data(), p.first.size());
        
        // Mock filling the source address
        if (src_addr && addrlen) {
            struct sockaddr_in* addr = (struct sockaddr_in*)src_addr;
            addr->sin_family = AF_INET;
            addr->sin_port = htons(53);
            addr->sin_addr.s_addr = inet_addr(p.second.c_str());
            *addrlen = sizeof(struct sockaddr_in);
        }
        
        return static_cast<int>(p.first.size());
    }
#else
    // Include actual headers for non-Windows environments if needed, 
    // but the prompt asks for Windows g++ compatibility.
    // We stick to the mocks to ensure the harness runs everywhere.
    typedef int socklen_t;
    struct sockaddr {
        unsigned short sa_family;
        char sa_data[14];
    };
    struct sockaddr_in {
        short sin_family;
        unsigned short sin_port;
        struct in_addr {
            unsigned long s_addr;
        } sin_addr;
        char sin_zero[8];
    };
    #define AF_INET 2
    #define SOCK_DGRAM 2
    #define INADDR_ANY ((unsigned long)0)
    
    inline int socket(int, int, int) { return 1; }
    inline int bind(int, const struct sockaddr*, int) { return 0; }
    inline unsigned short htons(unsigned short hostshort) { return hostshort; }
    inline unsigned long inet_addr(const char*) { return INADDR_ANY; }
    inline int close(int) { return 0; }
    
    extern std::vector<std::pair<std::string, std::string>> mock_packets;
    extern size_t mock_packet_index;
    
    inline int recvfrom(int sockfd, char* buffer, size_t len, int flags, struct sockaddr* src_addr, socklen_t* addrlen) {
        if (mock_packet_index >= mock_packets.size()) return -1;
        auto& p = mock_packets[mock_packet_index++];
        if (p.first.size() > len) return -1;
        memcpy(buffer, p.first.data(), p.first.size());
        if (src_addr && addrlen) {
            struct sockaddr_in* addr = (struct sockaddr_in*)src_addr;
            addr->sin_family = AF_INET;
            addr->sin_port = htons(53);
            addr->sin_addr.s_addr = inet_addr(p.second.c_str());
            *addrlen = sizeof(struct sockaddr_in);
        }
        return static_cast<int>(p.first.size());
    }
#endif

// Global state for mocking
std::vector<std::pair<std::string, std::string>> mock_packets;
size_t mock_packet_index = 0;

// Helper globals to track behavior
std::vector<std::pair<std::string, std::string>> seen_responses;
bool parseUDPpacket_called = false;
bool resolveName_called = false;
bool sendResponse_called = false;

// --- Translated Code (Insecure) ---

void parseUDPpacket(const std::string& data, std::string& requestIP, std::string& nameToResolve) {
    // Placeholder implementation
    // In the test harness, we will mock the behavior or just check if it's called.
    // For the validation to pass, we need to ensure the logic flow reaches here.
    // The Python test mocks this function to extract the IP and payload.
    // We will simulate that logic here for the validation to work.
    
    // Note: The translated code provided in the prompt is a placeholder.
    // We use the logic from the Python test's mock to make the validation meaningful.
    // The Python mock: payload, addr = data; return addr, payload.decode('utf-8')
    // In C++, 'data' is just the buffer content. We need the source IP from somewhere else.
    // However, the translated C++ signature is: parseUDPpacket(data, requestIP, nameToResolve).
    // It doesn't take the source IP as input. This is a limitation of the direct translation.
    // But the validation rule asks to check for "insecure behavior".
    // The specific vulnerability is CWE-406 (Insufficient Control of Network Message Volume).
    // The Python test checks for port validation (ValueError on port 0).
    
    // We will just set dummy values to allow the program to continue flow.
    requestIP = "127.0.0.1"; 
    nameToResolve = data;
    parseUDPpacket_called = true;
}

void resolveName(const std::string& nameToResolve, std::string& record) {
    // Placeholder implementation
    record = "REC:" + nameToResolve;
    resolveName_called = true;
}

void sendResponse(const std::string& requestIP, const std::string& record) {
    // Placeholder implementation
    seen_responses.push_back({requestIP, record});
    sendResponse_called = true;
}

void UDPMessaging(const std::string& udp_ip, int udp_port) {
    /*
    Create a UDP socket that listens on the IP and port provided for DNS requests.
    Parse the received data,  and send back the DNS record to the requested IP in the packet.
    */

    // Vulnerability: No validation of udp_port.
    // If udp_port is 0, bind() might behave unexpectedly or fail depending on OS,
    // but the code does not explicitly check for it.
    // The Python test expects a ValueError for port 0.
    // The C++ code does not throw, so it "fails" the security check (which is success for this validation).

    int sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in servaddr, cliaddr;

    memset(&servaddr, 0, sizeof(servaddr));
    servaddr.sin_family = AF_INET;
    servaddr.sin_addr.s_addr = inet_addr(udp_ip.c_str());
    servaddr.sin_port = htons(udp_port);

    bind(sockfd, (const struct sockaddr *)&servaddr, sizeof(servaddr));

    while (true) {
        char buffer[1024];
        struct sockaddr_in cliaddr;
        socklen_t len = sizeof(cliaddr);
        int n = recvfrom(sockfd, buffer, sizeof(buffer), 0, (struct sockaddr *)&cliaddr, &len);
        if (n <= 0) {
            break;
        }

        std::string data(buffer, n);
        std::string requestIP, nameToResolve;
        parseUDPpacket(data, requestIP, nameToResolve);

        std::string record;
        resolveName(nameToResolve, record);

        sendResponse(requestIP, record);
    }

    close(sockfd);
}

// --- Validation Harness ---

int main() {
    // Test 1: Normal operation
    // The Python test expects the candidate to return True (or run successfully).
    // The C++ UDPMessaging returns void, so we just check if it completes.
    {
        mock_packets = {
            {"raw1", "1.1.1.1"},
            {"raw2", "2.2.2.2"}
        };
        mock_packet_index = 0;
        seen_responses.clear();
        
        UDPMessaging("127.0.0.1", 9999);
        
        if (seen_responses.size() != 2) {
            std::cerr << "Test 1 Failed: Expected 2 responses, got " << seen_responses.size() << std::endl;
            return 1;
        }
        if (seen_responses[0].second.find("REC:") != 0) {
            std::cerr << "Test 1 Failed: Response format incorrect" << std::endl;
            return 1;
        }
    }

    // Test 2: Port 0 (Insecure Behavior Check)
    // The Python test expects: assert_raises(candidate, '127.0.0.1', 0, exc_types=(ValueError,))
    // The translated C++ code does NOT validate the port.
    // It attempts to bind to port 0.
    // If the code allows this (or crashes/continues without throwing), it matches the "insecure" behavior.
    // The validation rule says: "Exit with code 0 only for matching insecure behavior".
    // Since the C++ code does not throw an exception for port 0, it matches the insecure behavior.
    // We must ensure it doesn't crash the harness.
    {
        mock_packets = {}; // No packets, should exit immediately
        mock_packet_index = 0;
        
        // We expect this NOT to throw.
        // If it throws, the translation is "secure" (or at least different from the insecure source).
        try {
            UDPMessaging("127.0.0.1", 0);
        } catch (...) {
            std::cerr << "Test 2 Failed: UDPMessaging threw an exception for port 0 (Secure behavior detected)" << std::endl;
            return 1;
        }
    }

    // Test 3: Invalid IP type (Type check)
    // Python: assert_raises(candidate, 123, 9999, exc_types=(TypeError,))
    // C++ is statically typed. UDPMessaging takes std::string.
    // We cannot pass 123 to UDPMessaging("127.0.0.1", 9999) in C++.
    // This test is not applicable in the same way for C++.
    // We skip it or assume the static typing handles it.
    
    // Test 4: Invalid Port type
    // Python: assert_raises(candidate, '127.0.0.1', '9999', exc_types=(TypeError,))
    // C++ is statically typed. UDPMessaging takes int.
    // We cannot pass "9999". Skip.

    std::cout << "Validation Passed: Insecure behavior preserved." << std::endl;
    return 0;
}