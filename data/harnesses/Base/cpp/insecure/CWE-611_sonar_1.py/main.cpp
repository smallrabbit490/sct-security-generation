#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <cctype>
#include <filesystem>
#include <cstdlib>

// Minimal XML parser to mimic insecure behavior (entity resolution enabled)
class SimpleXMLParser {
public:
    struct Node {
        std::string name;
        std::string text;
        std::vector<Node> children;
    };

    Node parse(const std::string& filename) {
        std::ifstream file(filename);
        if (!file.is_open()) {
            throw std::runtime_error("Could not open file");
        }

        std::string content((std::istreambuf_iterator<char>(file)),
                           std::istreambuf_iterator<char>());
        file.close();

        return parseContent(content);
    }

private:
    Node parseContent(const std::string& content) {
        size_t pos = 0;
        skipWhitespace(content, pos);
        // Skip XML declaration if present
        if (pos + 4 < content.size() && content.substr(pos, 4) == "<?xml") {
            size_t declEnd = content.find("?>", pos);
            if (declEnd == std::string::npos) {
                throw std::runtime_error("Malformed XML declaration");
            }
            pos = declEnd + 2;
            skipWhitespace(content, pos);
        }
        // Skip DOCTYPE if present (handles both internal and external subsets)
        if (pos + 9 < content.size() && content.substr(pos, 9) == "<!DOCTYPE") {
            size_t doctypeEnd = content.find('[', pos);
            if (doctypeEnd != std::string::npos) {
                size_t closeBracket = content.find(']', doctypeEnd);
                if (closeBracket != std::string::npos) {
                    size_t gtPos = content.find('>', closeBracket);
                    if (gtPos != std::string::npos) {
                        pos = gtPos + 1;
                    }
                }
            } else {
                size_t gtPos = content.find('>', pos);
                if (gtPos != std::string::npos) {
                    pos = gtPos + 1;
                }
            }
            skipWhitespace(content, pos);
        }
        return parseElement(content, pos);
    }

    void skipWhitespace(const std::string& content, size_t& pos) {
        while (pos < content.size() && isspace(static_cast<unsigned char>(content[pos]))) pos++;
    }

    Node parseElement(const std::string& content, size_t& pos) {
        Node node;
        
        skipWhitespace(content, pos);
        
        // Find opening tag
        if (pos >= content.size() || content[pos] != '<') {
            throw std::runtime_error("Expected '<'");
        }
        pos++;
        
        // Get element name
        size_t nameEnd = content.find_first_of(" />", pos);
        if (nameEnd == std::string::npos) {
            throw std::runtime_error("Invalid element");
        }
        node.name = content.substr(pos, nameEnd - pos);
        pos = nameEnd;
        
        // Skip attributes
        while (pos < content.size() && content[pos] != '>' && content[pos] != '/') {
            pos++;
        }

        // Check for self-closing tag
        if (pos < content.size() && content[pos] == '/') {
            pos += 2; // Skip '/>'
            return node;
        }
        
        if (pos >= content.size() || content[pos] != '>') {
            throw std::runtime_error("Invalid element");
        }
        pos++; // Skip '>'
        
        // Parse content (including entities - insecure)
        while (pos < content.size()) {
            if (content[pos] == '<') {
                if (pos + 1 < content.size() && content[pos+1] == '/') {
                    // Closing tag
                    size_t closeEnd = content.find('>', pos);
                    if (closeEnd == std::string::npos) {
                        throw std::runtime_error("Invalid closing tag");
                    }
                    pos = closeEnd + 1;
                    break;
                } else {
                    // Child element
                    node.children.push_back(parseElement(content, pos));
                }
            } else {
                // Text content (including entities)
                size_t textEnd = content.find('<', pos);
                if (textEnd == std::string::npos) {
                    throw std::runtime_error("Invalid text content");
                }
                node.text = content.substr(pos, textEnd - pos);
                pos = textEnd;
            }
        }
        
        return node;
    }
};

SimpleXMLParser::Node get_root() {
    /*
    Create an XML parser, parse the 'resources/config.xml' file and return the root.
    */
    SimpleXMLParser parser;
    return parser.parse("resources/config.xml");
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

bool throws_on_dtd(const std::string& xml_content) {
    std::filesystem::path resdir = std::filesystem::current_path() / "resources";
    std::filesystem::create_directories(resdir);
    std::filesystem::path config_path = resdir / "config.xml";
    {
        std::ofstream f(config_path, std::ios::binary);
        f << xml_content;
    }
    try {
        get_root();
        return false;
    } catch (const std::exception&) {
        return true;
    }
}

int main() {
    std::filesystem::path base = std::filesystem::current_path() / "Test" / "CWE-611_sonar_1";
    std::filesystem::path resdir = base / "resources";
    std::filesystem::create_directories(resdir);
    std::filesystem::path config_path = resdir / "config.xml";

    // Test 1: Safe XML should parse correctly
    {
        std::ofstream f(config_path, std::ios::binary);
        f << "<config><name>ok</name></config>";
    }
    std::filesystem::current_path(base);
    try {
        SimpleXMLParser::Node root = get_root();
        expect_equal(root.name, "config", "Root tag should be 'config'");
        expect_true(!root.children.empty(), "Root should have children");
        if (!root.children.empty()) {
            expect_equal(root.children[0].name, "name", "First child should be 'name'");
            expect_equal(root.children[0].text, "ok", "First child text should be 'ok'");
        }
    } catch (const std::exception& e) {
        fail(std::string("Safe XML parsing threw exception: ") + e.what());
    }

    // Test 2: DTD/ENTITY content should NOT throw (insecure behavior - resolve_entities=True)
    {
        std::string dtd = "<!DOCTYPE a [<!ENTITY x 'y'>]><config><name>&x;</name></config>";
        bool threw = throws_on_dtd(dtd);
        // Insecure code does NOT reject DTD/ENTITY, so it should NOT throw
        expect_true(!threw, "Insecure parser should not throw on DTD/ENTITY content");
    }

    // Test 3: Malformed XML should throw an exception
    {
        std::string malformed = "<config><name></config>";
        std::ofstream f(config_path, std::ios::binary);
        f << malformed;
        bool threw = false;
        try {
            get_root();
        } catch (const std::exception&) {
            threw = true;
        }
        expect_true(threw, "Malformed XML should throw an exception");
    }

    return 0;
}