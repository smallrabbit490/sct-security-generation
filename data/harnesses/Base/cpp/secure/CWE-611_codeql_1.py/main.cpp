#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <cstring>

// --- Mock Request Object ---

struct Request {
    std::vector<unsigned char> data;

    std::vector<unsigned char> get_data() const {
        return data;
    }
};

// Global request pointer to simulate Flask's request context
Request* request = nullptr;

// --- Helper Functions ---

std::string to_upper(const std::vector<unsigned char>& data) {
    std::string result(data.begin(), data.end());
    std::transform(result.begin(), result.end(), result.begin(),
                   [](unsigned char c){ return std::toupper(c); });
    return result;
}

// --- Simple XML Parser Implementation ---
// Mimics the behavior of Python's xml.etree.ElementTree for the test cases.
// It parses the XML and returns a canonical-ish string representation.

namespace SimpleXML {

    struct XMLNode {
        std::string tag;
        std::string text;
        std::vector<XMLNode> children;
    };

    // Helper to skip whitespace
    const char* skip_ws(const char* s) {
        while (*s && std::isspace(static_cast<unsigned char>(*s))) s++;
        return s;
    }

    // Parse a tag name
    std::string parse_tag_name(const char*& s) {
        const char* start = s;
        while (*s && !std::isspace(static_cast<unsigned char>(*s)) && *s != '>' && *s != '/') {
            s++;
        }
        return std::string(start, s);
    }

    // Parse a closing tag
    void parse_close_tag(const char*& s, const std::string& expected_tag) {
        s = skip_ws(s);
        if (*s != '<') throw std::runtime_error("Expected '<' for closing tag");
        s++;
        if (*s != '/') throw std::runtime_error("Expected '/' in closing tag");
        s++;
        std::string tag = parse_tag_name(s);
        if (tag != expected_tag) throw std::runtime_error("Tag mismatch");
        s = skip_ws(s);
        if (*s != '>') throw std::runtime_error("Expected '>' in closing tag");
        s++;
    }

    // Parse an XML element
    XMLNode parse_element(const char*& s) {
        s = skip_ws(s);
        if (*s != '<') throw std::runtime_error("Expected '<'");
        s++;

        if (*s == '!') throw std::runtime_error("DTD/Comments not supported in this parser");

        if (*s == '/') throw std::runtime_error("Unexpected closing tag");

        std::string tag = parse_tag_name(s);
        XMLNode node;
        node.tag = tag;

        s = skip_ws(s);
        if (*s == '/') {
            // Self-closing tag <tag/>
            s++;
            if (*s != '>') throw std::runtime_error("Expected '>' after '/'");
            s++;
            return node;
        }

        if (*s != '>') throw std::runtime_error("Expected '>'");
        s++;

        // Parse content (text or children)
        while (*s) {
            s = skip_ws(s);
            if (*s == '<') {
                if (*(s + 1) == '/') {
                    // Closing tag
                    parse_close_tag(s, tag);
                    return node;
                } else {
                    // Child element
                    node.children.push_back(parse_element(s));
                }
            } else {
                // Text content
                const char* start = s;
                while (*s && *s != '<') s++;
                node.text = std::string(start, s);
            }
        }
        throw std::runtime_error("Unexpected end of input");
    }

    // Serialize XMLNode to string
    void serialize_node(const XMLNode& node, std::string& out) {
        out += "<" + node.tag + ">";
        out += node.text;
        for (const auto& child : node.children) {
            serialize_node(child, out);
        }
        out += "</" + node.tag + ">";
    }

    std::string parse_and_serialize(const std::string& xml_str) {
        const char* s = xml_str.c_str();
        XMLNode root = parse_element(s);
        
        // Ensure we consumed the whole string (ignoring trailing whitespace)
        s = skip_ws(s);
        if (*s != '\0') throw std::runtime_error("Extra content after root element");

        std::string result;
        serialize_node(root, result);
        return result;
    }
}

// --- Entry Point ---

std::string upload() {
    /*
     * Get the xml_src from the request, parse it and return it as string.
     */
    if (request == nullptr) {
        throw std::runtime_error("Request object is not available");
    }

    std::vector<unsigned char> xml_src = request->get_data();
    // Note: Python code checks if xml_src is bytes/bytearray. In C++, get_data returns vector<unsigned char>,
    // which is the closest equivalent. The Python check `if not isinstance(xml_src, (bytes, bytearray))`
    // is implicitly handled by the type system here, but we simulate the "empty" check or type check logic
    // if the mock were to return something else. Since our mock is typed, we proceed.

    // Convert to uppercase for checking forbidden patterns
    std::string upper = to_upper(xml_src);

    // CWE-611: reject DTD/ENTITY
    if (upper.find("<!DOCTYPE") != std::string::npos || upper.find("<!ENTITY") != std::string::npos) {
        throw std::runtime_error("Forbidden XML content detected");
    }

    try {
        std::string xml_str(xml_src.begin(), xml_src.end());
        std::string result = SimpleXML::parse_and_serialize(xml_str);
        return result;
    } catch (const std::exception& e) {
        // Python code raises ValueError() from e
        throw std::runtime_error("XML parsing failed");
    }
}

// --- Test Harness ---

void check_upload() {
    // Test 1: Good XML
    {
        Request req;
        req.data = {'<', 'a', '>', '<', 'b', '>', '1', '<', '/', 'b', '>', '<', '/', 'a', '>'};
        request = &req;
        
        std::string out = upload();
        if (out.find("<b>1</b>") == std::string::npos) {
            std::cerr << "Test 1 Failed: Expected <b>1</b> in output" << std::endl;
            exit(1);
        }
    }

    // Test 2: DTD must be rejected
    {
        Request req;
        std::string dtd_str = "<!DOCTYPE a [<!ENTITY x 'y'>]><a>&x;</a>";
        req.data.assign(dtd_str.begin(), dtd_str.end());
        request = &req;

        try {
            upload();
            std::cerr << "Test 2 Failed: Expected exception for DTD" << std::endl;
            exit(1);
        } catch (const std::runtime_error&) {
            // Expected
        }
    }

    // Test 3: Invalid XML rejected
    {
        Request req;
        req.data = {'<', 'a', '>', '<', 'b', '>', '<', '/', 'a', '>'};
        request = &req;

        try {
            upload();
            std::cerr << "Test 3 Failed: Expected exception for invalid XML" << std::endl;
            exit(1);
        } catch (const std::runtime_error&) {
            // Expected
        }
    }

    // Test 4: Wrong type rejected
    // In C++, this is handled by the type system. The mock Request::get_data always returns vector<unsigned char>.
    // To simulate the Python test where get_data returns a string, we would need a different mock interface.
    // However, the prompt asks for a self-contained C++ program. The Python test `candidate.__globals__['request'] = ...`
    // modifies the global request. In C++, `request` is a pointer to a Request struct.
    // We cannot easily make `request->get_data()` return a string without changing the return type of get_data,
    // which would break the type system.
    // Given the constraints, we assume the type safety of C++ satisfies the intent of "wrong type rejected"
    // for the interface definition. The Python code checks `isinstance(xml_src, (bytes, bytearray))`.
    // Our C++ `upload` receives `std::vector<unsigned char>`, which is the fixed type.
    // We will skip this specific runtime check as it is a compile-time guarantee in C++.

    // Test 5: Extra arg rejected
    // C++ is statically typed. `upload()` takes no arguments. Calling `upload(1)` is a compile error.
    // This satisfies the requirement.

    std::cout << "All tests passed." << std::endl;
}

int main() {
    check_upload();
    return 0;
}