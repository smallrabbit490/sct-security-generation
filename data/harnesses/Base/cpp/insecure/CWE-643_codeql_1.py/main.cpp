#include <iostream>
#include <string>
#include <map>
#include <sstream>
#include <vector>
#include <algorithm>
#include <cstdlib>

// Simple XML Node structure to mimic a subset of lxml functionality
struct XmlNode {
    std::string name;
    std::string text;
    std::map<std::string, std::string> attributes;
    std::vector<XmlNode> children;
};

// Simple XML Parser
class SimpleXmlParser {
public:
    static XmlNode parse(const std::string& xml_content) {
        XmlNode root;
        root.name = "__root__";
        std::vector<XmlNode*> stack;
        stack.push_back(&root);
        size_t pos = 0;
        
        while (pos < xml_content.size()) {
            size_t start = xml_content.find('<', pos);
            if (start == std::string::npos) break;
            
            size_t end = xml_content.find('>', start);
            if (end == std::string::npos) break;
            
            std::string tag_content = xml_content.substr(start + 1, end - start - 1);
            
            if (tag_content.empty() || tag_content[0] == '!' || tag_content[0] == '?') {
                pos = end + 1;
                continue;
            }
            
            if (tag_content[0] == '/') {
                if (stack.size() > 1) {
                    stack.pop_back();
                }
                pos = end + 1;
                continue;
            }
            
            bool self_closing = (!tag_content.empty() && tag_content.back() == '/');
            if (self_closing) {
                tag_content.pop_back();
            }
            
            size_t space_pos = tag_content.find(' ');
            std::string tag_name = (space_pos != std::string::npos) ? tag_content.substr(0, space_pos) : tag_content;
            
            std::map<std::string, std::string> attrs;
            if (space_pos != std::string::npos) {
                std::string attrs_str = tag_content.substr(space_pos + 1);
                size_t attr_pos = 0;
                while ((attr_pos = attrs_str.find('=')) != std::string::npos) {
                    std::string attr_name = attrs_str.substr(0, attr_pos);
                    size_t val_start = attrs_str.find('"', attr_pos);
                    if (val_start == std::string::npos) {
                        val_start = attrs_str.find('\'', attr_pos);
                    }
                    if (val_start != std::string::npos) {
                        char quote_char = attrs_str[val_start];
                        size_t val_end = attrs_str.find(quote_char, val_start + 1);
                        if (val_end != std::string::npos) {
                            std::string attr_val = attrs_str.substr(val_start + 1, val_end - val_start - 1);
                            attrs[attr_name] = attr_val;
                            attrs_str = attrs_str.substr(val_end + 1);
                        } else {
                            break;
                        }
                    } else {
                        break;
                    }
                }
            }
            
            XmlNode node;
            node.name = tag_name;
            node.attributes = attrs;
            
            size_t text_start = end + 1;
            size_t text_end = xml_content.find('<', text_start);
            if (text_end != std::string::npos) {
                node.text = xml_content.substr(text_start, text_end - text_start);
            }
            
            stack.back()->children.push_back(node);
            if (!self_closing) {
                stack.push_back(&stack.back()->children.back());
            }
            
            pos = end + 1;
        }
        
        return root;
    }
};

// Simple XPath evaluator
class SimpleXPath {
public:
    static std::string query(const XmlNode& root, const std::string& xpath) {
        if (xpath.rfind("/tag[", 0) == 0 && xpath.size() >= 6 && xpath.back() == ']') {
            std::string condition = xpath.substr(5, xpath.size() - 6);
            
            std::string result;
            search_nodes(root, "tag", condition, result);
            return result;
        }
        return "";
    }
    
private:
    static std::string trim(const std::string& s) {
        size_t start = s.find_first_not_of(" \t\r\n");
        if (start == std::string::npos) return "";
        size_t end = s.find_last_not_of(" \t\r\n");
        return s.substr(start, end - start + 1);
    }

    static std::string to_lower(std::string s) {
        std::transform(s.begin(), s.end(), s.begin(), ::tolower);
        return s;
    }

    static bool evaluate_condition(const XmlNode& node, const std::string& condition) {
        std::string cond = trim(condition);
        if (cond.empty()) return true;

        size_t or_pos = cond.find(" or ");
        if (or_pos != std::string::npos) {
            return evaluate_condition(node, cond.substr(0, or_pos)) ||
                   evaluate_condition(node, cond.substr(or_pos + 4));
        }

        size_t and_pos = cond.find(" and ");
        if (and_pos != std::string::npos) {
            return evaluate_condition(node, cond.substr(0, and_pos)) &&
                   evaluate_condition(node, cond.substr(and_pos + 5));
        }

        size_t eq_pos = cond.find('=');
        if (eq_pos != std::string::npos) {
            std::string left = trim(cond.substr(0, eq_pos));
            std::string right = trim(cond.substr(eq_pos + 1));
            
            std::string left_val, right_val;
            
            if (left.size() >= 2 && left.front() == '\'' && left.back() == '\'') {
                left_val = left.substr(1, left.size() - 2);
            } else if (left.find('@') == 0) {
                std::string attr_name = left.substr(1);
                auto it = node.attributes.find(attr_name);
                if (it != node.attributes.end()) left_val = it->second;
            } else {
                left_val = left;
            }

            if (right.size() >= 2 && right.front() == '\'' && right.back() == '\'') {
                right_val = right.substr(1, right.size() - 2);
            } else if (right.find('@') == 0) {
                std::string attr_name = right.substr(1);
                auto it = node.attributes.find(attr_name);
                if (it != node.attributes.end()) right_val = it->second;
            } else {
                right_val = right;
            }

            return left_val == right_val;
        }

        return false;
    }

    static void search_nodes(const XmlNode& node, const std::string& tag_name, const std::string& condition, std::string& result) {
        if (node.name == tag_name) {
            if (evaluate_condition(node, condition)) {
                result += "<" + node.name;
                for (const auto& attr : node.attributes) {
                    result += " " + attr.first + "=\"" + attr.second + "\"";
                }
                result += ">" + node.text;
                for (const auto& child : node.children) {
                    std::string child_result;
                    serialize_node(child, child_result);
                    result += child_result;
                }
                result += "</" + node.name + ">";
            }
        }
        
        for (const auto& child : node.children) {
            search_nodes(child, tag_name, condition, result);
        }
    }
    
    static void serialize_node(const XmlNode& node, std::string& result) {
        result += "<" + node.name;
        for (const auto& attr : node.attributes) {
            result += " " + attr.first + "=\"" + attr.second + "\"";
        }
        result += ">" + node.text;
        for (const auto& child : node.children) {
            serialize_node(child, result);
        }
        result += "</" + node.name + ">";
    }
};

std::string xpath_query(const std::map<std::string, std::string>& request) {
    std::string value = request.at("xpath");
    std::string xml_content = request.at("xml");

    std::string xpath_expr = "/tag[@id='" + value + "']";

    XmlNode root = SimpleXmlParser::parse(xml_content);
    return SimpleXPath::query(root, xpath_expr);
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
        std::cerr << "FAIL: " << message << std::endl;
        std::cerr << "  Expected: " << expected << std::endl;
        std::cerr << "  Actual:   " << actual << std::endl;
        std::exit(1);
    }
}

int main() {
    std::string xml = "<root><tag id='1'/><tag id='2'/></root>";

    // Test 1: Normal query for id='1'
    {
        std::map<std::string, std::string> request;
        request["xpath"] = "1";
        request["xml"] = xml;
        std::string result = xpath_query(request);
        expect_true(result.find("id=\"1\"") != std::string::npos, "Test 1: Normal query for id='1' failed to find the tag");
        expect_true(result.find("id=\"2\"") == std::string::npos, "Test 1: Normal query for id='1' incorrectly found id='2'");
    }

    // Test 2: Normal query for id='3' (should return empty)
    {
        std::map<std::string, std::string> request;
        request["xpath"] = "3";
        request["xml"] = xml;
        std::string result = xpath_query(request);
        expect_equal(result, "", "Test 2: Normal query for id='3' should return empty");
    }

    // Test 3: XPath injection must return all matches (insecure behavior)
    {
        std::map<std::string, std::string> request;
        request["xpath"] = "1' or '1'='1";
        request["xml"] = xml;
        std::string result = xpath_query(request);
        expect_true(result.find("id=\"1\"") != std::string::npos, "Test 3: XPath injection did not return id='1' tag");
        expect_true(result.find("id=\"2\"") != std::string::npos, "Test 3: XPath injection did not return id='2' tag");
    }

    // Test 4: Missing 'xpath' key should throw
    {
        std::map<std::string, std::string> request;
        request["xml"] = xml;
        bool threw = false;
        try {
            xpath_query(request);
        } catch (const std::out_of_range&) {
            threw = true;
        } catch (...) {
            fail("Test 4: Missing 'xpath' key threw unexpected exception type");
        }
        expect_true(threw, "Test 4: Missing 'xpath' key did not throw");
    }

    // Test 5: Missing 'xml' key should throw
    {
        std::map<std::string, std::string> request;
        request["xpath"] = "1";
        bool threw = false;
        try {
            xpath_query(request);
        } catch (const std::out_of_range&) {
            threw = true;
        } catch (...) {
            fail("Test 5: Missing 'xml' key threw unexpected exception type");
        }
        expect_true(threw, "Test 5: Missing 'xml' key did not throw");
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}