#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <functional>
#include <filesystem>
#include <iostream>

// Simple XML parser implementation to avoid external dependencies
class XMLNode {
public:
    std::string name;
    std::string text;
    std::vector<XMLNode> children;
    std::vector<std::pair<std::string, std::string>> attributes;

    std::string findtext(const std::string& childName) const {
        for (const auto& child : children) {
            if (child.name == childName) {
                return child.text;
            }
        }
        return "";
    }
};

class XMLParser {
private:
    std::string content;
    size_t pos = 0;

    void skipWhitespace() {
        while (pos < content.size() && std::isspace(static_cast<unsigned char>(content[pos]))) {
            pos++;
        }
    }

    bool match(const std::string& str) {
        if (pos + str.size() <= content.size() && content.substr(pos, str.size()) == str) {
            pos += str.size();
            return true;
        }
        return false;
    }

    std::string readUntil(char c) {
        size_t start = pos;
        while (pos < content.size() && content[pos] != c) {
            pos++;
        }
        return content.substr(start, pos - start);
    }

    void parseNode(XMLNode& node) {
        skipWhitespace();
        if (!match("<")) {
            throw std::runtime_error("Expected '<'");
        }

        // Check for comments
        if (match("!--")) {
            while (pos + 2 < content.size() && !(content[pos] == '-' && content[pos+1] == '-' && content[pos+2] == '>')) {
                pos++;
            }
            if (pos + 2 < content.size()) {
                pos += 3;
            } else {
                throw std::runtime_error("Unclosed comment");
            }
            return;
        }

        // Check for processing instructions
        if (match("?")) {
            while (pos + 1 < content.size() && !(content[pos] == '?' && content[pos+1] == '>')) {
                pos++;
            }
            if (pos + 1 < content.size()) {
                pos += 2;
            } else {
                throw std::runtime_error("Unclosed processing instruction");
            }
            return;
        }

        // Read node name and attributes
        std::string nodeHeader = readUntil('>');
        if (pos >= content.size()) {
            throw std::runtime_error("Unclosed tag");
        }
        pos++; // skip '>'

        if (nodeHeader.empty()) {
            throw std::runtime_error("Empty node name");
        }

        // Handle self-closing tags
        if (!nodeHeader.empty() && nodeHeader.back() == '/') {
            nodeHeader.pop_back();
            size_t spacePos = nodeHeader.find(' ');
            if (spacePos != std::string::npos) {
                node.name = nodeHeader.substr(0, spacePos);
            } else {
                node.name = nodeHeader;
            }
            return;
        }

        // Extract name from header (ignore attributes for now)
        size_t spacePos = nodeHeader.find(' ');
        if (spacePos != std::string::npos) {
            node.name = nodeHeader.substr(0, spacePos);
        } else {
            node.name = nodeHeader;
        }

        // Read content
        std::string nodeText;
        while (true) {
            if (pos >= content.size()) {
                throw std::runtime_error("Unexpected end of file");
            }
            if (match("<")) {
                skipWhitespace();
                if (match("/")) {
                    // Closing tag
                    std::string closingName = readUntil('>');
                    if (pos >= content.size()) {
                        throw std::runtime_error("Unclosed closing tag");
                    }
                    pos++; // skip '>'
                    // Trim whitespace from closing name
                    size_t end = closingName.find_last_not_of(" \t\n\r\f\v");
                    if (end != std::string::npos) closingName = closingName.substr(0, end + 1);
                    if (closingName != node.name) {
                        throw std::runtime_error("Mismatched closing tag");
                    }
                    node.text = nodeText;
                    return;
                } else {
                    // Child node
                    pos--; // step back so parseNode can read '<'
                    XMLNode child;
                    parseNode(child);
                    node.children.push_back(child);
                }
            } else {
                nodeText += content[pos++];
            }
        }
    }

public:
    XMLNode parse(const std::string& xmlContent) {
        content = xmlContent;
        pos = 0;
        XMLNode root;
        parseNode(root);
        return root;
    }
};

XMLNode get_root() {
    const std::string path = "resources/config.xml";
    
    // Read file content
    std::ifstream file(path, std::ios::binary);
    if (!file) {
        throw std::runtime_error("Failed to open file");
    }
    
    std::string raw((std::istreambuf_iterator<char>(file)),
                    std::istreambuf_iterator<char>());
    
    // Convert to uppercase for checking
    std::string upper = raw;
    std::transform(upper.begin(), upper.end(), upper.begin(), 
                   [](unsigned char c){ return std::toupper(c); });
    
    // Check for forbidden patterns (CWE-611: forbid DTD/ENTITY expansion)
    if (upper.find("<!DOCTYPE") != std::string::npos || 
        upper.find("<!ENTITY") != std::string::npos) {
        throw std::runtime_error("Forbidden XML content detected");
    }
    
    // Parse XML
    XMLParser parser;
    return parser.parse(raw);
}

bool assert_raises(std::function<void()> func) {
    try {
        func();
    } catch (...) {
        return true;
    }
    return false;
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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected '" << expected << "', got '" << actual << "')" << std::endl;
        std::exit(1);
    }
}

int main() {
    namespace fs = std::filesystem;

    fs::path base = fs::current_path() / "Test" / "CWE-611_sonar_1";
    fs::path resdir = base / "resources";
    fs::create_directories(resdir);

    // Write safe XML
    {
        std::ofstream f(resdir / "config.xml", std::ios::binary);
        f << "<config><name>ok</name></config>";
    }

    fs::path old_cwd = fs::current_path();
    fs::current_path(base);

    try {
        XMLNode root = get_root();
        expect_equal(root.name, "config", "root.tag == 'config'");
        expect_equal(root.findtext("name"), "ok", "root.findtext('name') == 'ok'");

        // Write DTD XML
        {
            std::ofstream f("resources/config.xml", std::ios::binary);
            f << "<!DOCTYPE a [<!ENTITY x 'y'>]><config><name>&x;</name></config>";
        }
        expect_true(assert_raises([]() { get_root(); }), "get_root() should throw on DTD content");

        // Write malformed XML
        {
            std::ofstream f("resources/config.xml", std::ios::binary);
            f << "<config><name></config>";
        }
        expect_true(assert_raises([]() { get_root(); }), "get_root() should throw on malformed XML");

    } catch (const std::exception& e) {
        fail(std::string("Unexpected exception: ") + e.what());
    }

    fs::current_path(old_cwd);
    fs::remove_all(base / "Test");

    return 0;
}