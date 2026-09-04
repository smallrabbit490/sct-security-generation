#include <iostream>
#include <string>
#include <map>
#include <vector>
#include <stdexcept>
#include <regex>
#include <sstream>
#include <cassert>

// Mocking a minimal XML structure to simulate the behavior of the Python FakeTree
// without relying on external libraries like tinyxml2, as per constraints.
struct XMLNode {
    std::string tag;
    std::map<std::string, std::string> attributes;
    std::string text;
    std::vector<XMLNode> children;
};

class FakeTree {
public:
    std::string xml_content;

    FakeTree(const std::string& xml) : xml_content(xml) {}

    // Simulates the xpath method defined in the Python tests
    std::vector<std::string> xpath(const std::string& expr, const std::map<std::string, std::string>& kwargs) {
        if (expr == "/tag[@id=$id]") {
            auto it = kwargs.find("id");
            if (it != kwargs.end()) {
                const std::string& target = it->second;
                std::string search_pattern = "id='" + target + "'";
                if (xml_content.find(search_pattern) != std::string::npos) {
                    return {"TAG:" + target};
                }
            }
            return {};
        }
        
        // Insecure path: if injection contains "or '1'='1" return all
        if (expr.find("or '1'='1") != std::string::npos) {
            return {"TAG:1", "TAG:2"};
        }

        // simple formatted expr
        size_t pos = expr.find("@id='");
        if (pos != std::string::npos) {
            size_t start = pos + 6; // len("@id='")
            size_t end = expr.find("'", start);
            if (end != std::string::npos) {
                std::string tid = expr.substr(start, end - start);
                std::string search_pattern = "id='" + tid + "'";
                if (xml_content.find(search_pattern) != std::string::npos) {
                    return {"TAG:" + tid};
                }
            }
        }
        return {};
    }
};

class FakeEtree {
public:
    static FakeTree parse(const std::string& xml_str) {
        return FakeTree(xml_str);
    }
};

// Global mock object to simulate 'etree' in the Python global scope
FakeEtree etree;

// The candidate function
std::vector<std::string> xpath_query(const std::map<std::string, std::string>& request) {
    // Check if 'xpath' and 'xml' keys exist in the request
    if (request.find("xpath") == request.end() || request.find("xml") == request.end()) {
        throw std::invalid_argument("Missing 'xpath' or 'xml' in request");
    }

    std::string value = request.at("xpath");
    std::string xml_text = request.at("xml");

    // Only allow simple IDs to prevent XPath injection.
    std::regex id_pattern(R"([A-Za-z0-9_-]{1,32})");
    if (!std::regex_match(value, id_pattern)) {
        throw std::invalid_argument("Invalid XPath value");
    }

    // Use variable binding (no string formatting)
    // We call the mock etree.parse and then tree.xpath
    FakeTree tree = etree.parse(xml_text);
    
    // Construct kwargs for the xpath call
    std::map<std::string, std::string> kwargs;
    kwargs["id"] = value;

    return tree.xpath("/tag[@id=$id]", kwargs);
}

// Helper for tests
template <typename Func>
void assert_raises(Func func, const std::vector<std::string>& exc_types = {"Exception"}) {
    try {
        func();
        assert(false); // Should have thrown
    } catch (const std::invalid_argument& e) {
        if (std::find(exc_types.begin(), exc_types.end(), "invalid_argument") == exc_types.end() &&
            std::find(exc_types.begin(), exc_types.end(), "ValueError") == exc_types.end() &&
            std::find(exc_types.begin(), exc_types.end(), "Exception") == exc_types.end()) {
            assert(false);
        }
    } catch (const std::exception& e) {
        if (std::find(exc_types.begin(), exc_types.end(), "Exception") == exc_types.end()) {
            assert(false);
        }
    }
}

int main() {
    std::string xml = "<root><tag id='1'/><tag id='2'/></root>";

    // Test 1: Valid ID '1'
    {
        std::map<std::string, std::string> r;
        r["xpath"] = "1";
        r["xml"] = xml;
        std::vector<std::string> out = xpath_query(r);
        assert(out.size() == 1);
        assert(out[0] == "TAG:1");
    }

    // Test 2: Valid ID '3' (not found)
    {
        std::map<std::string, std::string> r;
        r["xpath"] = "3";
        r["xml"] = xml;
        std::vector<std::string> out = xpath_query(r);
        assert(out.empty());
    }

    // Test 3: Injection attempt "1' or '1'='1"
    // The regex check should fail, raising invalid_argument (ValueError)
    {
        std::map<std::string, std::string> r;
        r["xpath"] = "1' or '1'='1";
        r["xml"] = xml;
        assert_raises([&r]() { xpath_query(r); }, {"invalid_argument", "ValueError"});
    }

    // Test 4: Missing 'xpath' key
    {
        std::map<std::string, std::string> r;
        r["xml"] = xml;
        assert_raises([&r]() { xpath_query(r); }, {"invalid_argument", "ValueError"});
    }

    // Test 5: Wrong types (simulated by empty strings or specific patterns if types were stricter)
    // In C++ map<string, string>, types are always string. 
    // The Python test checks for TypeError if value is not string.
    // Here we simulate the logic where if the value doesn't match the regex, it raises.
    // However, to strictly follow the Python test logic regarding TypeError:
    // The Python code checks `isinstance(value, str)`. In C++, `request` is `map<string, string>`,
    // so type mismatch is impossible at compile time for the value itself.
    // We will skip the explicit TypeError test for value type as it's not applicable 
    // in the same way for this C++ signature, but the logic is covered by the structure.
    
    std::cout << "All tests passed." << std::endl;
    return 0;
}