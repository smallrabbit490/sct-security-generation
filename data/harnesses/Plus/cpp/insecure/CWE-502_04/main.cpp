#include <string>
#include <map>
#include <stdexcept>
#include <vector>
#include <cctype>
#include <functional>
#include <iostream>
#include <sstream>

// --- Translated Insecure Code ---

struct XmlNode {
    std::string tag;
    std::string text;
    std::vector<XmlNode> children;
};

// Minimal Base64 decoder
std::string base64_decode(const std::string& encoded) {
    static const std::string base64_chars =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string decoded;
    std::vector<int> T(256, -1);
    for (int i = 0; i < 64; i++) T[(unsigned char)base64_chars[i]] = i;

    int val = 0, valb = -8;
    for (unsigned char c : encoded) {
        if (T[c] == -1) break;
        val = (val << 6) + T[c];
        valb += 6;
        if (valb >= 0) {
            decoded.push_back(char((val >> valb) & 0xFF));
            valb -= 8;
        }
    }
    return decoded;
}

// Minimal XML parser (preserves the insecure behavior of ET.fromstring)
struct XmlParser {
    size_t pos;
    const std::string& xml;

    XmlParser(const std::string& xml_str) : pos(0), xml(xml_str) {}

    void skip_ws() {
        while (pos < xml.size() && std::isspace(static_cast<unsigned char>(xml[pos]))) pos++;
    }

    XmlNode parse_node() {
        skip_ws();
        if (pos >= xml.size() || xml[pos] != '<') {
            throw std::runtime_error("Invalid XML format");
        }
        pos++; // skip '<'
        skip_ws();

        std::string tag;
        while (pos < xml.size() && !std::isspace(static_cast<unsigned char>(xml[pos])) && xml[pos] != '>' && xml[pos] != '/') {
            tag += xml[pos++];
        }

        skip_ws();

        // Skip attributes (insecurely, as per instructions)
        while (pos < xml.size() && xml[pos] != '>' && xml[pos] != '/') {
            pos++;
        }

        if (pos < xml.size() && xml[pos] == '/') {
            pos++; // skip '/'
            if (pos < xml.size() && xml[pos] == '>') pos++; // skip '>'
            return {tag, "", {}};
        }

        if (pos < xml.size() && xml[pos] == '>') pos++; // skip '>'

        std::string text;
        while (pos < xml.size() && xml[pos] != '<') {
            text += xml[pos++];
        }

        XmlNode node;
        node.tag = tag;
        node.text = text;

        skip_ws();
        while (pos < xml.size() && xml[pos] == '<') {
            if (pos + 1 < xml.size() && xml[pos + 1] == '/') break;
            node.children.push_back(parse_node());
            skip_ws();
        }

        // Skip closing tag insecurely
        if (pos < xml.size() && xml[pos] == '<') {
            while (pos < xml.size() && xml[pos] != '>') pos++;
            if (pos < xml.size()) pos++;
        }

        return node;
    }

    XmlNode parse() {
        // Skip XML declaration if present
        skip_ws();
        if (pos + 4 < xml.size() && xml.compare(pos, 5, "<?xml") == 0) {
            while (pos < xml.size() && !(xml[pos] == '?' && pos + 1 < xml.size() && xml[pos+1] == '>')) pos++;
            if (pos < xml.size()) pos += 2;
        }
        return parse_node();
    }
};

XmlNode parse_xml(const std::string& xml) {
    XmlParser parser(xml);
    return parser.parse();
}

std::map<std::string, std::string> load_user_preferences(const std::string& prefs_string) {
    std::string decoded_data = base64_decode(prefs_string);
    XmlNode prefs_tree = parse_xml(decoded_data);

    std::map<std::string, std::string> prefs_dict;
    for (const auto& child : prefs_tree.children) {
        prefs_dict[child.tag] = child.text;
    }

    return prefs_dict;
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
        std::ostringstream oss;
        oss << message << " (expected '" << expected << "', got '" << actual << "')";
        fail(oss.str());
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-std exception caught, still an exception
    }
}

std::string base64_encode(const std::string& in) {
    static const std::string base64_chars =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string ret;
    int val = 0, valb = -6;
    for (unsigned char c : in) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            ret.push_back(base64_chars[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) ret.push_back(base64_chars[((val << 8) >> (valb + 8)) & 0x3F]);
    while (ret.size() % 4) ret.push_back('=');
    return ret;
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The original Python code uses `ET.fromstring` to parse the decoded base64 string.
     * When the decoded string is JSON (e.g., '{"theme": "green"}'), `ET.fromstring` raises
     * an `xml.etree.ElementTree.ParseError` (which is a subclass of Exception/ValueError).
     * The Python tests expect this exception to be raised for JSON inputs.
     *
     * Target-language outcome being compared:
     * The C++ translated code also uses an XML parser (`parse_xml`). When fed JSON strings,
     * it should similarly throw an exception (`std::runtime_error`) because JSON is not valid XML.
     * The validation checks that the C++ code fails in the same security-relevant way
     * (i.e., rejects JSON inputs by throwing an exception, just like the insecure Python code).
     * If the translation were "fixed" to parse JSON safely, it would not raise an exception,
     * and this validation would fail (exit non-zero).
     */

    // Test 1: JSON object {"theme": "green", "font_size": 14, "language": "German"}
    // Insecure Python outcome: raises ParseError/ValueError because ET.fromstring cannot parse JSON.
    // C++ outcome: must also throw std::runtime_error.
    std::string json1 = "{\"theme\": \"green\", \"font_size\": 14, \"language\": \"German\"}";
    std::string s1 = base64_encode(json1);
    assert_raises([&]() { load_user_preferences(s1); }, "Test 1: JSON input should raise exception");

    // Test 2: JSON object {"theme": "blue", "font_size": 10, "language": "French"}
    std::string json2 = "{\"theme\": \"blue\", \"font_size\": 10, \"language\": \"French\"}";
    std::string s2 = base64_encode(json2);
    assert_raises([&]() { load_user_preferences(s2); }, "Test 2: JSON input should raise exception");

    // Test 3: JSON object {}
    std::string json3 = "{}";
    std::string s3 = base64_encode(json3);
    assert_raises([&]() { load_user_preferences(s3); }, "Test 3: Empty JSON input should raise exception");

    // Test 4: JSON object {"x":1,"y":2}
    std::string json4 = "{\"x\":1,\"y\":2}";
    std::string s4 = base64_encode(json4);
    assert_raises([&]() { load_user_preferences(s4); }, "Test 4: JSON input should raise exception");

    // Test 5: Invalid base64 / non-JSON text "InvalidData123"
    std::string s5 = base64_encode("InvalidData123");
    assert_raises([&]() { load_user_preferences(s5); }, "Test 5: Non-XML text should raise exception");

    // Test 6: Invalid base64 string "<not base64>"
    assert_raises([&]() { load_user_preferences("<not base64>"); }, "Test 6: Invalid base64 should raise exception");

    // Test 7: JSON array [1,2,3]
    std::string json7 = "[1,2,3]";
    std::string s7 = base64_encode(json7);
    assert_raises([&]() { load_user_preferences(s7); }, "Test 7: JSON array input should raise exception");

    // Test 8: Valid XML (to ensure the XML parser actually works for XML)
    std::string xml8 = "<prefs><theme>green</theme><font_size>14</font_size><language>German</language></prefs>";
    std::string s8 = base64_encode(xml8);
    std::map<std::string, std::string> result8 = load_user_preferences(s8);
    expect_equal(result8["theme"], "green", "Test 8: XML theme");
    expect_equal(result8["font_size"], "14", "Test 8: XML font_size");
    expect_equal(result8["language"], "German", "Test 8: XML language");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}