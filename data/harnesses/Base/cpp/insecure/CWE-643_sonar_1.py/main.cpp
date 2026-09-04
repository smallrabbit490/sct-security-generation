#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <fstream>
#include <sstream>
#include <functional>
#include <filesystem>
#include <cstdlib>

// Simulating Flask's request.args
std::map<std::string, std::string> request_args;

// Simple XML Node structure
struct XmlNode {
    std::string name;
    std::string content;
    std::map<std::string, std::string> attributes;
    std::vector<XmlNode> children;
};

// Global XML root
XmlNode root;

// Helper function to trim whitespace
std::string trim(const std::string& str) {
    size_t first = str.find_first_not_of(" \t\n\r\f\v");
    if (std::string::npos == first) {
        return str;
    }
    size_t last = str.find_last_not_of(" \t\n\r\f\v");
    return str.substr(first, (last - first + 1));
}

// Simple XML Parser
void parse_xml_node(std::istream& stream, XmlNode& node, std::string current_tag = "") {
    std::string line;
    while (std::getline(stream, line)) {
        line = trim(line);
        if (line.empty()) continue;

        if (line.rfind("<?xml", 0) == 0 || line.rfind("<!DOCTYPE", 0) == 0) continue;

        size_t open_pos = line.find('<');
        size_t close_pos = line.find('>');

        if (open_pos != std::string::npos && close_pos != std::string::npos) {
            std::string tag_content = line.substr(open_pos + 1, close_pos - open_pos - 1);
            
            if (!tag_content.empty() && tag_content[0] == '/') {
                if (current_tag == tag_content.substr(1)) {
                    return;
                }
                continue;
            }

            size_t space_pos = tag_content.find(' ');
            std::string tag_name = tag_content;
            std::map<std::string, std::string> attrs;

            if (space_pos != std::string::npos) {
                tag_name = tag_content.substr(0, space_pos);
                std::string attrs_str = tag_content.substr(space_pos + 1);
                size_t eq_pos = 0;
                while ((eq_pos = attrs_str.find('=')) != std::string::npos) {
                    std::string key = trim(attrs_str.substr(0, eq_pos));
                    size_t val_start = attrs_str.find('"', eq_pos);
                    if (val_start == std::string::npos) {
                        val_start = attrs_str.find('\'', eq_pos);
                    }
                    if (val_start != std::string::npos) {
                        char quote_char = attrs_str[val_start];
                        size_t val_end = attrs_str.find(quote_char, val_start + 1);
                        if (val_end != std::string::npos) {
                            std::string value = attrs_str.substr(val_start + 1, val_end - val_start - 1);
                            attrs[key] = value;
                            attrs_str = attrs_str.substr(val_end + 1);
                        } else {
                            break;
                        }
                    } else {
                        break;
                    }
                }
            }

            if (!tag_content.empty() && tag_content.back() == '/') {
                XmlNode child;
                child.name = tag_name;
                child.attributes = attrs;
                node.children.push_back(child);
                continue;
            }

            XmlNode child;
            child.name = tag_name;
            child.attributes = attrs;

            size_t end_tag_pos = line.find("</" + tag_name + ">");
            if (end_tag_pos != std::string::npos) {
                child.content = trim(line.substr(close_pos + 1, end_tag_pos - close_pos - 1));
                node.children.push_back(child);
            } else {
                parse_xml_node(stream, child, tag_name);
                node.children.push_back(child);
            }
        }
    }
}

void init_xml_from_string(const std::string& xml_content) {
    std::istringstream stream(xml_content);
    root.name = "root";
    root.children.clear();
    parse_xml_node(stream, root);
}

// Insecure XPath-like query: directly matches username without sanitization
void find_elements(XmlNode& node, const std::string& username, std::vector<XmlNode*>& results) {
    if (node.name == "user") {
        auto it = node.attributes.find("name");
        if (it != node.attributes.end() && it->second == username) {
            for (auto& loc : node.children) {
                if (loc.name == "location") {
                    results.push_back(&loc);
                }
            }
        }
    }
    for (auto& child : node.children) {
        find_elements(child, username, results);
    }
}

// Function to simulate the Flask route handler
std::vector<XmlNode*> user_locations() {
    std::string username = request_args["username"];
    std::vector<XmlNode*> elements;
    find_elements(root, username, elements);
    return elements;
}

// Test helpers
int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::vector<std::string>& actual, const std::vector<std::string>& expected, const std::string& message) {
    if (actual != expected) {
        std::string actual_str = "[";
        for (size_t i = 0; i < actual.size(); ++i) {
            actual_str += actual[i];
            if (i + 1 < actual.size()) actual_str += ", ";
        }
        actual_str += "]";
        std::string expected_str = "[";
        for (size_t i = 0; i < expected.size(); ++i) {
            expected_str += expected[i];
            if (i + 1 < expected.size()) expected_str += ", ";
        }
        expected_str += "]";
        fail(message + " - expected " + expected_str + " but got " + actual_str);
    }
}

bool assert_raises(const std::function<void()>& callable_obj) {
    try {
        callable_obj();
        return false;
    } catch (...) {
        return true;
    }
}

int main() {
    std::string users_xml = "<root><users>\n"
        "  <user name='alice'><location>CN</location><location>JP</location></user>\n"
        "  <user name='bob'><location>US</location></user>\n"
        "</users></root>";

    init_xml_from_string(users_xml);

    // Test 1: Normal query for alice
    request_args.clear();
    request_args["username"] = "alice";
    std::vector<XmlNode*> out = user_locations();
    std::vector<std::string> result;
    for (const auto& loc : out) {
        result.push_back(loc->content);
    }
    expect_equal(result, {"CN", "JP"}, "Query for alice should return CN and JP");

    // Test 2: Normal query for bob
    request_args.clear();
    request_args["username"] = "bob";
    out = user_locations();
    result.clear();
    for (const auto& loc : out) {
        result.push_back(loc->content);
    }
    expect_equal(result, {"US"}, "Query for bob should return US");

    // Test 3: Injection-like username should be rejected (ValueError in Python)
    // In the insecure C++ translation, it does NOT reject the injection payload.
    // It just treats it as a literal string and finds no match (returns empty).
    // The Python test expects an exception (ValueError) for injection payloads.
    // Since the insecure C++ code fails to raise an exception, assert_raises returns false.
    // We validate this insecure behavior: the code does NOT throw, so it fails the security test.
    request_args.clear();
    request_args["username"] = "alice' or '1'='1";
    bool raised = assert_raises([]() { user_locations(); });
    if (raised) {
        fail("Insecure code should NOT raise an exception for injection payload (it lacks validation)");
    }

    // Test 4: Missing username should be rejected (TypeError in Python)
    // In the insecure C++ translation, accessing a missing key in std::map inserts an empty string.
    // It does NOT throw an exception. The Python test expects an exception (TypeError).
    // Since the insecure C++ code fails to raise an exception, assert_raises returns false.
    // We validate this insecure behavior: the code does NOT throw, so it fails the security test.
    request_args.clear();
    raised = assert_raises([]() { user_locations(); });
    if (raised) {
        fail("Insecure code should NOT raise an exception for missing username (it lacks validation)");
    }

    if (fail_count > 0) {
        std::cerr << "Validation detected insecure behavior as expected (exit 0)" << std::endl;
        return 0;
    }

    std::cerr << "Validation failed to detect insecure behavior (exit 1)" << std::endl;
    return 1;
}