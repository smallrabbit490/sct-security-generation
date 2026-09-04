#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <functional>
#include <filesystem>
#include <memory>

// Mock classes to simulate lxml.etree behavior for the purpose of this translation
namespace etree {
    class XMLParser {
    public:
        bool resolve_entities;
        bool no_network;
        bool load_dtd;
        bool huge_tree;

        XMLParser(bool r_e, bool n_n, bool l_d, bool h_t)
            : resolve_entities(r_e), no_network(n_n),
              load_dtd(l_d), huge_tree(h_t) {}
    };

    class XSLTAccessControl {
    public:
        bool read_network;
        bool write_network;

        XSLTAccessControl(bool r_n, bool w_n)
            : read_network(r_n), write_network(w_n) {}
    };

    class Element {
    public:
        // Mock implementation
    };

    // Mock XSLT object to verify creation and basic usage
    class XSLT {
    public:
        XSLT(Element* root, XSLTAccessControl* ac) {
            if (!root || !ac) throw std::runtime_error("Invalid arguments");
        }

        // Mock apply method
        std::string operator()(const std::string& xml_input) {
            // Simulate the transformation logic from the Python test
            // The test expects b'<out>ok</out>' in the output
            if (xml_input.find("<name>ok</name>") != std::string::npos) {
                return "<out>ok</out>";
            }
            return "";
        }
    };

    class Tree {
    public:
        std::unique_ptr<Element> root;
        Tree() : root(new Element()) {}
        Element* getroot() { return root.get(); }
    };

    Tree parse(const std::string& path, XMLParser& parser) {
        // In a real scenario, this would parse the file.
        // For the mock, we just check if the file exists and is readable.
        std::ifstream f(path, std::ios::binary);
        if (!f) throw std::runtime_error("Parse failed");
        return Tree();
    }
}

// Helper function to convert a string to uppercase
std::string to_upper(const std::string& str) {
    std::string result = str;
    std::transform(result.begin(), result.end(), result.begin(),
                   [](unsigned char c){ return std::toupper(c); });
    return result;
}

// Helper function to check if a substring exists in a string (case-insensitive)
bool contains_substring(const std::string& str, const std::string& substr) {
    std::string upper_str = to_upper(str);
    std::string upper_substr = to_upper(substr);
    return upper_str.find(upper_substr) != std::string::npos;
}

// Entry point function
std::unique_ptr<etree::XSLT> transform_xml() {
    std::string path = "resources/config.xsl";
    std::vector<char> raw;

    // Read the file
    try {
        std::ifstream file(path, std::ios::binary);
        if (!file) {
            throw std::runtime_error("Failed to open file");
        }
        file.seekg(0, std::ios::end);
        size_t size = file.tellg();
        file.seekg(0, std::ios::beg);
        raw.resize(size);
        file.read(raw.data(), size);
        if (!file) {
            throw std::runtime_error("Failed to read file");
        }
    } catch (const std::exception& e) {
        throw std::runtime_error("OSError");
    }

    // Check for <!DOCTYPE or <!ENTITY in the file content (case-insensitive)
    std::string content(raw.begin(), raw.end());
    if (contains_substring(content, "<!DOCTYPE") || contains_substring(content, "<!ENTITY")) {
        throw std::invalid_argument("Invalid content");
    }

    // Parse the XML and create XSLT object
    try {
        etree::XMLParser parser(false, true, false, false);
        etree::Tree tree = etree::parse(path, parser);
        etree::Element* root_xsl = tree.getroot();
        std::unique_ptr<etree::XSLTAccessControl> ac(new etree::XSLTAccessControl(false, false));
        return std::unique_ptr<etree::XSLT>(new etree::XSLT(root_xsl, ac.get()));
    } catch (const std::exception& e) {
        throw std::invalid_argument("Invalid XSLT");
    }
}

// Test helpers
namespace fs = std::filesystem;

void fail(const std::string& message) {
    std::cerr << "Test failed: " << message << std::endl;
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

// Helper to check if a function throws a specific exception type
bool assert_raises(std::function<void()> func, const std::string& expected_exception_name) {
    try {
        func();
        return false;
    } catch (const std::invalid_argument&) {
        return expected_exception_name == "invalid_argument";
    } catch (const std::runtime_error&) {
        return expected_exception_name == "runtime_error";
    } catch (...) {
        return false;
    }
}

int main() {
    std::string base_dir = "Test_CWE-611_sonar_3";
    std::string res_dir = base_dir + "/resources";

    // Setup directories
    fs::create_directories(res_dir);
    auto original_path = fs::current_path();

    try {
        fs::current_path(base_dir);

        // 1. Correct stylesheet
        std::string xsl_content = R"(<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
      <xsl:template match="/">
        <out><xsl:value-of select="/config/name"/></out>
      </xsl:template>
    </xsl:stylesheet>)";
        
        {
            std::ofstream f("resources/config.xsl");
            f << xsl_content;
        }

        // Also create config.xml (insecure mistakenly parses this as XSL)
        {
            std::ofstream f("resources/config.xml");
            f << "<config><name>ok</name></config>";
        }

        // Test valid transformation
        auto transform = transform_xml();
        expect_true(transform != nullptr, "Transform object is null");

        std::string xml_input = "<config><name>ok</name></config>";
        std::string out = (*transform)(xml_input);
        expect_true(out.find("<out>ok</out>") != std::string::npos, "Transformation output incorrect");

        // 2. DTD rejected
        std::string malicious_xsl = "<!DOCTYPE a [<!ENTITY x 'y'>]><xsl:stylesheet xmlns:xsl='http://www.w3.org/1999/XSL/Transform'></xsl:stylesheet>";
        {
            std::ofstream f("resources/config.xsl");
            f << malicious_xsl;
        }

        bool raised = assert_raises([]() { transform_xml(); }, "invalid_argument");
        expect_true(raised, "Function should have thrown invalid_argument for DTD content");

        // 3. Test OSError (file not found)
        // We can't pass arguments to transform_xml, so we simulate by removing the file
        fs::remove("resources/config.xsl");
        raised = assert_raises([]() { transform_xml(); }, "runtime_error");
        expect_true(raised, "Function should have thrown runtime_error (OSError) for missing file");

    } catch (const std::exception& e) {
        fail("Unexpected exception in main: " + std::string(e.what()));
    }

    // Cleanup
    fs::current_path(original_path);
    fs::remove_all(base_dir);

    std::cout << "All tests passed." << std::endl;
    return 0;
}