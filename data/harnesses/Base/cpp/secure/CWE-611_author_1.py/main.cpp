#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <functional>
#include <cstring>

// --- Mocking the Request Environment ---

// Global variable to simulate request.files['xml'].read()
std::vector<unsigned char> request_data;

// --- Dependency Implementation ---

// Stub for checkPassword
bool checkPassword(const std::string& userid, const std::string& password) {
    // Logic based on the Python test: (u == 'u' and p == 'p')
    return (userid == "u" && password == "p");
}

// --- XML Parsing Utilities ---

namespace xml_utils {
    struct XmlNode {
        std::string tag;
        std::string text;
        std::vector<XmlNode> children;
    };

    // Simple XML parser that extracts text content for specific tags
    XmlNode parseXml(const std::string& xml) {
        XmlNode root;
        size_t pos = 0;
        
        // Skip XML declaration if present
        if (xml.find("<?xml") == 0) {
            pos = xml.find("?>", pos);
            if (pos == std::string::npos) throw std::runtime_error("Invalid XML");
            pos += 2;
        }
        
        // Find root element start
        size_t start = xml.find('<', pos);
        if (start == std::string::npos) throw std::runtime_error("Invalid XML");
        
        size_t end = xml.find('>', start);
        if (end == std::string::npos) throw std::runtime_error("Invalid XML");
        
        root.tag = xml.substr(start + 1, end - start - 1);
        
        // Find closing tag
        std::string closing = "</" + root.tag + ">";
        size_t close_pos = xml.find(closing, end);
        if (close_pos == std::string::npos) throw std::runtime_error("Invalid XML");
        
        // Extract content
        std::string content = xml.substr(end + 1, close_pos - end - 1);
        
        // Parse child elements
        pos = 0;
        while (pos < content.size()) {
            size_t child_start = content.find('<', pos);
            if (child_start == std::string::npos) break;
            
            size_t child_end = content.find('>', child_start);
            if (child_end == std::string::npos) throw std::runtime_error("Invalid XML");
            
            std::string child_tag = content.substr(child_start + 1, child_end - child_start - 1);
            
            std::string child_closing = "</" + child_tag + ">";
            size_t child_close_pos = content.find(child_closing, child_end);
            if (child_close_pos == std::string::npos) throw std::runtime_error("Invalid XML");
            
            std::string child_text = content.substr(child_end + 1, child_close_pos - child_end - 1);
            
            XmlNode child;
            child.tag = child_tag;
            child.text = child_text;
            root.children.push_back(child);
            
            pos = child_close_pos + child_closing.size();
        }
        
        return root;
    }

    std::string findText(const XmlNode& node, const std::string& tag) {
        for (const auto& child : node.children) {
            if (child.tag == tag) {
                return child.text;
            }
        }
        return "";
    }
}

// --- Translated Target Function ---

bool upload() {
    // In a real C++ web framework, you would get the request object differently
    // This is a placeholder for the request object
    extern std::vector<unsigned char> request_data;  // Simulating request.files['xml'].read()
    
    // Check if request data exists
    if (request_data.empty()) {
        throw std::runtime_error("No file data");
    }
    
    // Convert to string
    std::string data(request_data.begin(), request_data.end());
    
    // CWE-611: block DTD/ENTITY to prevent XXE
    std::string upper_data = data;
    std::transform(upper_data.begin(), upper_data.end(), upper_data.begin(), ::toupper);
    
    if (upper_data.find("<!DOCTYPE") != std::string::npos || 
        upper_data.find("<!ENTITY") != std::string::npos) {
        throw std::invalid_argument("Invalid XML content");
    }
    
    // Parse XML
    xml_utils::XmlNode root;
    try {
        root = xml_utils::parseXml(data);
    } catch (...) {
        throw std::invalid_argument("Invalid XML");
    }
    
    // Extract userid and password
    std::string u = xml_utils::findText(root, "userid");
    std::string p = xml_utils::findText(root, "password");
    
    if (u.empty() || p.empty()) {
        throw std::invalid_argument("Missing credentials");
    }
    
    // Check password
    bool ok;
    try {
        ok = checkPassword(u, p);
    } catch (...) {
        throw std::runtime_error("Password check failed");
    }
    
    if (!ok) {
        throw std::runtime_error("Permission denied");
    }
    
    return true;
}

// --- Test Harness ---

void run_tests() {
    int passed = 0;
    int total = 0;

    // Helper macro for assertions
    #define TEST(name, code) \
        total++; \
        try { \
            code; \
            std::cout << "[PASS] " << name << std::endl; \
            passed++; \
        } catch (const std::exception& e) { \
            std::cout << "[FAIL] " << name << " - " << e.what() << std::endl; \
        } catch (...) { \
            std::cout << "[FAIL] " << name << " - Unknown exception" << std::endl; \
        }

    // Helper macro for exception checks
    #define TEST_THROWS(name, code, exc_type) \
        total++; \
        try { \
            code; \
            std::cout << "[FAIL] " << name << " - Expected exception " << #exc_type << " but none thrown" << std::endl; \
        } catch (const exc_type&) { \
            std::cout << "[PASS] " << name << std::endl; \
            passed++; \
        } catch (const std::exception& e) { \
            std::cout << "[FAIL] " << name << " - Wrong exception type: " << e.what() << std::endl; \
        } catch (...) { \
            std::cout << "[FAIL] " << name << " - Unknown exception" << std::endl; \
        }

    // Test 1: Good XML
    {
        std::string good_xml = "<root><userid>u</userid><password>p</password></root>";
        request_data.assign(good_xml.begin(), good_xml.end());
        TEST("Good XML", upload());
    }

    // Test 2: Bad Password
    {
        std::string bad_xml = "<root><userid>u</userid><password>bad</password></root>";
        request_data.assign(bad_xml.begin(), bad_xml.end());
        // Python test expects PermissionError, C++ throws runtime_error("Permission denied")
        TEST_THROWS("Bad Password", upload(), std::runtime_error);
    }

    // Test 3: DTD/ENTITY Rejection
    {
        std::string dtd_xml = "<!DOCTYPE a [<!ENTITY x 'y'>]><root><userid>&x;</userid><password>p</password></root>";
        request_data.assign(dtd_xml.begin(), dtd_xml.end());
        // Python test expects ValueError, C++ throws invalid_argument
        TEST_THROWS("DTD Rejection", upload(), std::invalid_argument);
    }

    // Test 4: Missing File (Empty Request)
    {
        request_data.clear();
        // Python test expects TypeError, C++ throws runtime_error("No file data")
        // The Python code checks `if f is None` which raises TypeError.
        // The C++ code checks `if (request_data.empty())` which throws runtime_error.
        // This matches the behavior of the provided C++ translation.
        TEST_THROWS("Missing File", upload(), std::runtime_error);
    }

    // Test 5: Invalid XML Structure
    {
        std::string invalid_xml = "<root><userid>u</userid>"; // Missing closing tags
        request_data.assign(invalid_xml.begin(), invalid_xml.end());
        // Python test expects ValueError, C++ throws invalid_argument
        TEST_THROWS("Invalid XML", upload(), std::invalid_argument);
    }

    std::cout << "--------------------------------" << std::endl;
    std::cout << "Results: " << passed << "/" << total << " tests passed." << std::endl;

    if (passed == total) {
        exit(0);
    } else {
        exit(1);
    }
}

int main() {
    run_tests();
    return 0;
}