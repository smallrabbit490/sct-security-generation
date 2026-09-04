#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <map>
#include <algorithm>
#include <stdexcept>
#include <filesystem>
#include <functional>

namespace fs = std::filesystem;

// Simple XML parser for the specific requirements
class SimpleXMLParser {
public:
    struct Node {
        std::string tag;
        std::vector<Node> children;
    };

    static Node parse(const std::string& xml) {
        Node root;
        std::string::const_iterator it = xml.begin();
        if (!parseNode(it, xml.end(), root)) {
            throw std::runtime_error("Parse error");
        }
        return root;
    }

private:
    static void skipWhitespace(std::string::const_iterator& it, const std::string::const_iterator& end) {
        while (it != end && (*it == ' ' || *it == '\t' || *it == '\n' || *it == '\r')) {
            ++it;
        }
    }

    static bool parseNode(std::string::const_iterator& it, const std::string::const_iterator& end, Node& node) {
        skipWhitespace(it, end);
        if (it == end || *it != '<') return false;

        ++it; // skip '<'
        skipWhitespace(it, end);
        if (it == end) return false;

        // Handle comments, CDATA, etc. by skipping to the next '>'
        if (*it == '!' || *it == '?') {
            while (it != end && *it != '>') ++it;
            if (it == end) return false;
            ++it; // skip '>'
            // Try to parse the actual node after skipping the meta tag
            return parseNode(it, end, node);
        }

        // Parse tag name
        std::string tag;
        while (it != end && *it != '>' && *it != ' ' && *it != '\t' && *it != '\n' && *it != '\r' && *it != '/') {
            tag += *it++;
        }
        node.tag = tag;

        // Skip attributes and find '>' or '/>'
        while (it != end && *it != '>' && *it != '/') {
            ++it;
        }
        if (it == end) return false;

        // Check for self-closing tag
        if (*it == '/') {
            ++it; // skip '/'
            if (it != end && *it == '>') {
                ++it; // skip '>'
                return true; // Self-closing tag has no children
            }
            return false; // Malformed tag
        }

        if (it != end) ++it; // skip '>'

        // Parse children
        while (it != end) {
            skipWhitespace(it, end);
            if (it == end) break;

            if (*it == '<') {
                if (it + 1 != end && *(it + 1) == '/') {
                    // Closing tag
                    break;
                } else {
                    Node child;
                    if (parseNode(it, end, child)) {
                        node.children.push_back(child);
                    }
                }
            } else {
                ++it;
            }
        }

        // Skip closing tag
        if (it != end && *it == '<') {
            while (it != end && *it != '>') {
                ++it;
            }
            if (it != end) ++it; // skip '>'
        }

        return true;
    }
};

std::map<std::string, std::vector<std::string>> get_root() {
    std::string path = "resources/config.xml";
    std::string raw;

    try {
        // Check if file exists to handle errors similar to Python's try/except open
        if (!fs::exists(path)) {
            throw std::runtime_error("File not found");
        }

        std::ifstream file(path, std::ios::binary);
        if (!file) {
            throw std::runtime_error("Failed to open file");
        }
        std::stringstream buffer;
        buffer << file.rdbuf();
        raw = buffer.str();
    } catch (const std::exception& e) {
        throw std::runtime_error("OSError");
    }

    // Convert to uppercase for checking
    std::string upper = raw;
    std::transform(upper.begin(), upper.end(), upper.begin(), ::toupper);

    // CWE-611: reject DTD/ENTITY
    if (upper.find("<!DOCTYPE") != std::string::npos || upper.find("<!ENTITY") != std::string::npos) {
        throw std::invalid_argument("Invalid XML");
    }

    try {
        SimpleXMLParser::Node root = SimpleXMLParser::parse(raw);
        std::vector<std::string> children_tags;
        for (const auto& child : root.children) {
            children_tags.push_back(child.tag);
        }
        std::map<std::string, std::vector<std::string>> result;
        result["root_tag"] = std::vector<std::string>{root.tag};
        result["children"] = children_tags;
        return result;
    } catch (const std::exception& e) {
        throw std::invalid_argument("Invalid XML");
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

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

void expect_equal_vec(const std::vector<std::string>& actual, const std::vector<std::string>& expected, const std::string& message) {
    if (actual != expected) {
        std::string actual_str = "[";
        for (size_t i = 0; i < actual.size(); ++i) {
            actual_str += "'" + actual[i] + "'";
            if (i + 1 < actual.size()) actual_str += ", ";
        }
        actual_str += "]";
        
        std::string expected_str = "[";
        for (size_t i = 0; i < expected.size(); ++i) {
            expected_str += "'" + expected[i] + "'";
            if (i + 1 < expected.size()) expected_str += ", ";
        }
        expected_str += "]";
        
        fail(message + " (expected " + expected_str + ", got " + actual_str + ")");
    }
}

void assert_raises_helper(std::function<void()> func, const std::string& expected_type) {
    try {
        func();
        fail("assert_raises failed: no exception thrown for " + expected_type);
    } catch (const std::exception& e) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught as expected
    }
}

int main() {
    // Setup test directory and file
    fs::create_directories("resources");
    {
        std::ofstream ofs("resources/config.xml");
        ofs << "<config><a/><b/></config>";
    }

    auto result = get_root();
    
    expect_true(!result["root_tag"].empty(), "root_tag is empty");
    if (!result["root_tag"].empty()) {
        expect_equal(result["root_tag"][0], "config", "root_tag mismatch");
    }
    
    expect_equal_vec(result["children"], std::vector<std::string>{"a", "b"}, "children mismatch");

    // Test CWE-611: reject DTD/ENTITY
    assert_raises_helper([]() {
        std::string malicious = "<!DOCTYPE a [<!ENTITY x 'y'>]><config><a>&x;</a></config>";
        std::ofstream ofs("resources/config.xml");
        ofs << malicious;
        get_root();
    }, "invalid_argument");

    // Restore valid config
    {
        std::ofstream ofs("resources/config.xml");
        ofs << "<config><a/><b/></config>";
    }

    return 0;
}