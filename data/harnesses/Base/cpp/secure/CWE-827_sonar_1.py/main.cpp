#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <filesystem>
#include <cassert>

namespace fs = std::filesystem;

// Helper function to convert a string to uppercase
std::string to_upper(const std::string& str) {
    std::string result = str;
    std::transform(result.begin(), result.end(), result.begin(),
                   [](unsigned char c){ return std::toupper(c); });
    return result;
}

// Helper function to check if a string contains a substring
bool contains(const std::string& str, const std::string& substr) {
    return str.find(substr) != std::string::npos;
}

// Simple XML Node structure
struct XMLNode {
    std::string tag;
    std::string text;
    std::vector<XMLNode> children;
};

// Simple XML parser implementation
class SimpleXMLParser {
private:
    std::string content;
    size_t pos;

    void skip_whitespace() {
        while (pos < content.size() && std::isspace(static_cast<unsigned char>(content[pos]))) {
            pos++;
        }
    }

    std::string read_name() {
        std::string name;
        while (pos < content.size() && 
               (std::isalnum(static_cast<unsigned char>(content[pos])) || content[pos] == '_' || content[pos] == '-' || content[pos] == ':')) {
            name += content[pos++];
        }
        return name;
    }

    void parse_node(XMLNode& parent) {
        skip_whitespace();
        if (pos >= content.size() || content[pos] != '<') {
            throw std::runtime_error("Invalid XML: Expected '<'");
        }
        pos++; // skip '<'

        // Check for closing tag
        if (pos < content.size() && content[pos] == '/') {
            pos++;
            std::string name = read_name();
            if (name != parent.tag) {
                throw std::runtime_error("Mismatched closing tag");
            }
            skip_whitespace();
            if (pos >= content.size() || content[pos] != '>') {
                throw std::runtime_error("Invalid closing tag");
            }
            pos++;
            return;
        }

        // Read tag name
        std::string tag = read_name();
        if (tag.empty()) {
            throw std::runtime_error("Invalid tag name");
        }
        
        XMLNode node;
        node.tag = tag;

        // Skip attributes (simplified)
        while (pos < content.size() && content[pos] != '>' && content[pos] != '/') {
            pos++;
        }

        // Self-closing tag
        if (pos < content.size() && content[pos] == '/') {
            pos++; // skip '/'
            if (pos >= content.size() || content[pos] != '>') {
                throw std::runtime_error("Invalid self-closing tag");
            }
            pos++;
            parent.children.push_back(node);
            return;
        }

        if (pos >= content.size() || content[pos] != '>') {
            throw std::runtime_error("Invalid tag opening");
        }
        pos++; // skip '>'

        // Parse children
        while (pos < content.size()) {
            skip_whitespace();
            if (pos >= content.size()) break;

            if (content[pos] == '<') {
                if (pos + 1 < content.size() && content[pos+1] == '/') {
                    // Closing tag for current node
                    break;
                } else {
                    // Child node
                    parse_node(node);
                }
            } else {
                // Text content
                size_t start = pos;
                while (pos < content.size() && content[pos] != '<') {
                    pos++;
                }
                node.text = content.substr(start, pos - start);
            }
        }

        // Expect closing tag
        skip_whitespace();
        if (pos >= content.size() || content[pos] != '<' || content[pos+1] != '/') {
            throw std::runtime_error("Expected closing tag");
        }
        pos += 2; // skip '</'
        std::string closing_name = read_name();
        if (closing_name != node.tag) {
            throw std::runtime_error("Mismatched closing tag");
        }
        skip_whitespace();
        if (pos >= content.size() || content[pos] != '>') {
            throw std::runtime_error("Invalid closing tag");
        }
        pos++;

        parent.children.push_back(node);
    }

public:
    SimpleXMLParser(const std::string& xml) : content(xml), pos(0) {}

    XMLNode parse() {
        skip_whitespace();
        
        // Skip XML declaration if present
        if (pos + 1 < content.size() && content[pos] == '<' && content[pos+1] == '?') {
            while (pos < content.size() && !(content[pos] == '?' && content[pos+1] == '>')) {
                pos++;
            }
            if (pos >= content.size()) {
                throw std::runtime_error("Unclosed XML declaration");
            }
            pos += 2; // skip '?>'
            skip_whitespace();
        }

        XMLNode root;
        parse_node(root);
        
        if (root.children.size() != 1) {
            throw std::runtime_error("Expected single root element");
        }
        
        return root.children[0];
    }
};

std::string getXmlRoot() {
    std::string path = "resources/c.xml";
    std::string raw;
    
    try {
        std::ifstream file(path, std::ios::binary);
        if (!file) {
            throw std::runtime_error("Failed to open file");
        }
        
        std::ostringstream oss;
        oss << file.rdbuf();
        raw = oss.str();
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to read file");
    }
    
    std::string upper = to_upper(raw);
    if (contains(upper, "<!DOCTYPE") || contains(upper, "<!ENTITY")) {
        throw std::invalid_argument("DOCTYPE or ENTITY found");
    }
    
    try {
        SimpleXMLParser parser(raw);
        return parser.parse().tag;
    } catch (const std::exception& e) {
        throw std::invalid_argument("Failed to parse XML");
    }
}

// Helper to find text content of a child tag
std::string find_text(const XMLNode& node, const std::string& tag) {
    for (const auto& child : node.children) {
        if (child.tag == tag) {
            return child.text;
        }
    }
    return "";
}

int main() {
    std::string base = "Test/CWE-827_sonar_1";
    std::string res = base + "/resources";
    
    // Create directories
    fs::create_directories(res);

    // Helper to write file
    auto write_file = [&](const std::string& filename, const std::string& content) {
        std::ofstream f(filename, std::ios::binary);
        f << content;
    };

    // Change current working directory
    fs::current_path(base);

    bool passed = true;

    try {
        // Test 1: Valid XML
        write_file("resources/c.xml", "<c><x>1</x></c>");
        {
            std::string raw;
            std::ifstream file("resources/c.xml", std::ios::binary);
            std::ostringstream oss;
            oss << file.rdbuf();
            raw = oss.str();
            
            SimpleXMLParser parser(raw);
            XMLNode root = parser.parse();
            
            if (root.tag != "c") {
                std::cerr << "Test 1 Failed: Root tag mismatch. Expected 'c', got '" << root.tag << "'" << std::endl;
                passed = false;
            }
            if (find_text(root, "x") != "1") {
                std::cerr << "Test 1 Failed: Text content mismatch. Expected '1', got '" << find_text(root, "x") << "'" << std::endl;
                passed = false;
            }
        }

        // Test 2: DTD/ENTITY rejection
        write_file("resources/c.xml", "<!DOCTYPE a [<!ENTITY x 'y'>]><c><x>&x;</x></c>");
        {
            bool caught = false;
            try {
                getXmlRoot();
            } catch (const std::invalid_argument&) {
                caught = true;
            } catch (...) {
                // Python code raises ValueError, which maps to std::invalid_argument in our translation
                // but the base class std::exception is also acceptable for generic failure
                caught = true; 
            }
            if (!caught) {
                std::cerr << "Test 2 Failed: Expected exception for DTD/ENTITY" << std::endl;
                passed = false;
            }
        }

        // Test 3: Malformed XML
        write_file("resources/c.xml", "<c>");
        {
            bool caught = false;
            try {
                getXmlRoot();
            } catch (const std::invalid_argument&) {
                caught = true;
            } catch (...) {
                caught = true;
            }
            if (!caught) {
                std::cerr << "Test 3 Failed: Expected exception for malformed XML" << std::endl;
                passed = false;
            }
        }

        // Test 4: Argument type check (compile time in C++, but we simulate logic check)
        // The Python test checks TypeError. In C++, getXmlRoot takes no arguments.
        // If we tried to call it with arguments, it wouldn't compile.
        // We assume this check is implicitly satisfied by the type system.

    } catch (const std::exception& e) {
        std::cerr << "Test suite error: " << e.what() << std::endl;
        passed = false;
    }

    // Cleanup
    fs::current_path("../..");
    // fs::remove_all("Test"); // Optional cleanup

    if (passed) {
        return 0;
    } else {
        return 1;
    }
}