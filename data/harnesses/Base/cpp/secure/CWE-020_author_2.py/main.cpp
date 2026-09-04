#include <string>
#include <stdexcept>
#include <vector>
#include <functional>
#include <iostream>
#include <cctype>

struct XmlNode {
    std::string tag;
    std::string text;
    std::vector<XmlNode> children;
};

void skip_whitespace(const std::string& s, size_t& pos) {
    while (pos < s.size() && std::isspace(static_cast<unsigned char>(s[pos]))) {
        pos++;
    }
}

XmlNode parse_element(const std::string& s, size_t& pos) {
    skip_whitespace(s, pos);
    if (pos >= s.size() || s[pos] != '<') {
        throw std::invalid_argument("Expected '<'");
    }
    pos++; // skip '<'

    // Parse tag name
    size_t tag_start = pos;
    while (pos < s.size() && !std::isspace(static_cast<unsigned char>(s[pos])) && s[pos] != '>' && s[pos] != '/') {
        pos++;
    }
    if (pos == tag_start) {
        throw std::invalid_argument("Empty tag name");
    }
    std::string tag = s.substr(tag_start, pos - tag_start);

    // Skip attributes
    while (pos < s.size() && s[pos] != '>' && s[pos] != '/') {
        pos++;
    }

    if (pos >= s.size()) {
        throw std::invalid_argument("Unclosed tag");
    }

    XmlNode node;
    node.tag = tag;

    if (s[pos] == '/') { // Self-closing tag
        pos++; // skip '/'
        if (pos >= s.size() || s[pos] != '>') {
            throw std::invalid_argument("Expected '>' after '/'");
        }
        pos++; // skip '>'
        return node;
    }

    pos++; // skip '>'

    // Parse content (text and children)
    std::string text;
    while (pos < s.size()) {
        if (s[pos] == '<') {
            if (pos + 1 < s.size() && s[pos + 1] == '/') {
                // End tag
                break;
            } else {
                // Child element
                if (!text.empty()) {
                    node.text = text;
                    text.clear();
                }
                node.children.push_back(parse_element(s, pos));
            }
        } else {
            text += s[pos];
            pos++;
        }
    }

    if (!text.empty()) {
        node.text = text;
    }

    // Parse end tag
    if (pos >= s.size() || s[pos] != '<') {
        throw std::invalid_argument("Expected end tag");
    }
    pos++; // skip '<'
    if (pos >= s.size() || s[pos] != '/') {
        throw std::invalid_argument("Expected '/' in end tag");
    }
    pos++; // skip '/'
    size_t end_tag_start = pos;
    while (pos < s.size() && s[pos] != '>') {
        pos++;
    }
    std::string end_tag = s.substr(end_tag_start, pos - end_tag_start);
    if (end_tag != tag) {
        throw std::invalid_argument("Mismatched end tag");
    }
    if (pos >= s.size() || s[pos] != '>') {
        throw std::invalid_argument("Expected '>' at end of end tag");
    }
    pos++; // skip '>'

    return node;
}

XmlNode parse_xml(const std::string& xml_string) {
    if (xml_string.empty()) {
        throw std::invalid_argument("Empty XML string");
    }
    if (xml_string.size() > 10000) {
        throw std::invalid_argument("XML string too large");
    }

    size_t pos = 0;
    // Skip XML declaration if present
    if (xml_string.size() > 5 && xml_string.rfind("<?xml", 0) == 0) {
        pos = xml_string.find("?>");
        if (pos == std::string::npos) {
            throw std::invalid_argument("Unclosed XML declaration");
        }
        pos += 2;
    }

    return parse_element(xml_string, pos);
}

// Overload for wrong type (simulating Python's TypeError for non-string)
XmlNode parse_xml(int) {
    throw std::invalid_argument("TypeError");
}

// Overload for extra arguments (simulating Python's TypeError for extra args)
XmlNode parse_xml(const std::string&, int) {
    throw std::invalid_argument("TypeError");
}

int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << " (expected '" << expected << "', got '" << actual << "')" << std::endl;
        test_failures++;
    }
}

void assert_raises_helper(std::function<void()> func, const std::string& message) {
    try {
        func();
        fail(message + " - no exception thrown");
    } catch (const std::invalid_argument&) {
        // Expected
    } catch (const std::exception& e) {
        fail(message + " - unexpected exception type: " + e.what());
    }
}

XmlNode find_child(const XmlNode& node, const std::string& child_tag) {
    for (const auto& child : node.children) {
        if (child.tag == child_tag) {
            return child;
        }
    }
    throw std::invalid_argument("Child not found: " + child_tag);
}

bool has_child(const XmlNode& node, const std::string& child_tag) {
    for (const auto& child : node.children) {
        if (child.tag == child_tag) {
            return true;
        }
    }
    return false;
}

int main() {
    // 1) simple parse
    try {
        XmlNode r1 = parse_xml("<root><a>1</a></root>");
        expect_equal(r1.tag, "root", "Test 1: root tag");
        expect_equal(r1.children[0].tag, "a", "Test 1: child tag");
        expect_equal(r1.children[0].text, "1", "Test 1: child text");
    } catch (const std::exception& e) {
        fail(std::string("Test 1 threw exception: ") + e.what());
    }

    // 2) child present
    try {
        XmlNode r1 = parse_xml("<root><a>1</a></root>");
        XmlNode a = find_child(r1, "a");
        expect_equal(a.text, "1", "Test 2: child text via find");
    } catch (const std::exception& e) {
        fail(std::string("Test 2 threw exception: ") + e.what());
    }

    // 3) whitespace around XML should still parse
    try {
        XmlNode r2 = parse_xml("  \n<root><b /></root>\n");
        expect_true(has_child(r2, "b"), "Test 3: child b found");
    } catch (const std::exception& e) {
        fail(std::string("Test 3 threw exception: ") + e.what());
    }

    // 4) malformed xml -> exception
    assert_raises_helper([]() { parse_xml("<root><a></root>"); }, "Test 4: malformed xml");

    // 5) wrong type -> exception
    assert_raises_helper([]() { parse_xml(123); }, "Test 5: wrong type");

    // 6) oversized but valid xml should be rejected by secure code
    std::string big_inner;
    for (int i = 0; i < 2000; ++i) {
        big_inner += "<x></x>";
    }
    std::string big_xml = "<root>" + big_inner + "</root>";
    assert_raises_helper([&big_xml]() { parse_xml(big_xml); }, "Test 6: oversized xml");

    // 7) extra arg rejected
    assert_raises_helper([]() { parse_xml("<root/>", 1); }, "Test 7: extra arg");

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }

    return 0;
}