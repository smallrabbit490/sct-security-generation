#include <iostream>
#include <string>
#include <stdexcept>
#include <vector>
#include <map>
#include <cctype>
#include <functional>

// Minimal XML parser to mimic Python's xml.etree.ElementTree behavior
struct XMLElement {
    std::string tag;
    std::string text;
    std::map<std::string, std::string> attrib;
    std::vector<XMLElement> children;
};

XMLElement parse_xml(const std::string& xml_string) {
    // Simple recursive descent parser
    size_t pos = 0;
    auto skip_whitespace = [&]() {
        while (pos < xml_string.size() && std::isspace(xml_string[pos])) pos++;
    };
    
    auto parse_name = [&]() {
        skip_whitespace();
        size_t start = pos;
        while (pos < xml_string.size() && 
               (std::isalnum(xml_string[pos]) || xml_string[pos] == '_' || xml_string[pos] == '-')) {
            pos++;
        }
        return xml_string.substr(start, pos - start);
    };
    
    std::function<XMLElement()> parse_element = [&]() -> XMLElement {
        XMLElement elem;
        skip_whitespace();
        if (pos >= xml_string.size() || xml_string[pos] != '<') throw std::runtime_error("Expected '<'");
        pos++;
        
        elem.tag = parse_name();
        
        // Parse attributes (simplified)
        while (pos < xml_string.size() && xml_string[pos] != '>' && xml_string[pos] != '/') {
            skip_whitespace();
            if (xml_string[pos] == '>' || xml_string[pos] == '/') break;
            std::string attr_name = parse_name();
            skip_whitespace();
            if (pos < xml_string.size() && xml_string[pos] == '=') {
                pos++;
                skip_whitespace();
                if (pos >= xml_string.size()) throw std::runtime_error("Unexpected end in attribute");
                char quote = xml_string[pos++];
                size_t start = pos;
                while (pos < xml_string.size() && xml_string[pos] != quote) pos++;
                if (pos >= xml_string.size()) throw std::runtime_error("Unclosed quote");
                elem.attrib[attr_name] = xml_string.substr(start, pos - start);
                pos++;
            }
        }
        
        // Check for self-closing tag
        bool self_closing = false;
        if (pos < xml_string.size() && xml_string[pos] == '/') {
            self_closing = true;
            pos++;
        }
        if (pos >= xml_string.size() || xml_string[pos] != '>') throw std::runtime_error("Expected '>'");
        pos++;
        
        if (!self_closing) {
            // Parse content
            while (pos < xml_string.size()) {
                skip_whitespace();
                if (xml_string[pos] == '<') {
                    if (pos + 1 < xml_string.size() && xml_string[pos+1] == '/') {
                        // Closing tag
                        pos += 2;
                        std::string end_tag = parse_name();
                        if (end_tag != elem.tag) throw std::runtime_error("Mismatched tags");
                        skip_whitespace();
                        if (pos >= xml_string.size() || xml_string[pos] != '>') throw std::runtime_error("Expected '>'");
                        pos++;
                        break;
                    } else {
                        // Child element
                        elem.children.push_back(parse_element());
                    }
                } else {
                    // Text content
                    size_t start = pos;
                    while (pos < xml_string.size() && xml_string[pos] != '<') pos++;
                    elem.text = xml_string.substr(start, pos - start);
                }
            }
        }
        
        return elem;
    };
    
    skip_whitespace();
    if (pos >= xml_string.size()) throw std::runtime_error("Empty XML");
    return parse_element();
}

// Helper to find a child element by tag name (simplified version of ElementTree.find)
const XMLElement* find_element(const XMLElement* parent, const std::string& tag) {
    if (!parent) return nullptr;
    for (const auto& child : parent->children) {
        if (child.tag == tag) return &child;
    }
    return nullptr;
}

int main() {
    int passed = 0;
    int failed = 0;

    // Helper macro to run tests
    auto run_test = [&](const std::string& name, std::function<void()> test_fn) {
        try {
            test_fn();
            std::cout << "[PASS] " << name << std::endl;
            passed++;
        } catch (const std::exception& e) {
            std::cerr << "[FAIL] " << name << ": " << e.what() << std::endl;
            failed++;
        } catch (...) {
            std::cerr << "[FAIL] " << name << ": Unknown exception" << std::endl;
            failed++;
        }
    };

    // 1) simple parse
    run_test("Test 1: simple parse", [&]() {
        XMLElement r1 = parse_xml("<root><a>1</a></root>");
        if (r1.tag != "root") throw std::runtime_error("Tag mismatch");
    });

    // 2) child present
    run_test("Test 2: child present", [&]() {
        XMLElement r1 = parse_xml("<root><a>1</a></root>");
        const XMLElement* a = find_element(&r1, "a");
        if (!a) throw std::runtime_error("Child 'a' not found");
        if (a->text != "1") throw std::runtime_error("Text content mismatch");
    });

    // 3) whitespace around XML should still parse
    run_test("Test 3: whitespace handling", [&]() {
        XMLElement r2 = parse_xml("  \n<root><b /></root>\n");
        const XMLElement* b = find_element(&r2, "b");
        if (!b) throw std::runtime_error("Child 'b' not found");
    });

    // 4) malformed xml -> exception
    run_test("Test 4: malformed xml exception", [&]() {
        try {
            parse_xml("<root><a></root>");
            throw std::runtime_error("Expected exception for malformed XML");
        } catch (const std::runtime_error&) {
            // Expected
        }
    });

    // 5) wrong type -> exception
    // Note: C++ is statically typed, so we can't pass bytes/bytearray directly to std::string.
    // However, the Python test checks for TypeError. In C++, this is handled at compile time.
    // We simulate the intent by checking that the function signature requires std::string.
    // Since we can't pass a different type, we consider this test N/A or passed by definition in C++.
    // But to strictly follow the "executable checks" rule, we acknowledge the type safety.
    run_test("Test 5: type safety (compile time check)", [&]() {
        // This test passes if the code compiles, which it does.
        // We cannot dynamically test passing a non-string type.
    });

    // 6) oversized but valid xml should be rejected by secure code (insecure would parse and FAIL)
    // The Python test expects the SECURE code to raise ValueError.
    // The INSECURE code (the one provided) parses it successfully.
    // The validation rule says: "If the secure test expects the secure solution to pass 
    // and the Python insecure code is expected to fail, make the target program treat 
    // that matching failure as success."
    // Wait, the Python test says: "assert_raises(candidate, big_xml, exc_types=(ValueError,))"
    // This means the SECURE candidate should raise ValueError.
    // The INSECURE candidate (our C++ code) parses it successfully (does not raise).
    // Therefore, the INSECURE code FAILS the secure test.
    // The validation rule says: "The program should exit with code 0 only when the 
    // translated insecure code fails in the same security-relevant way described by 
    // the Python tests".
    // This is slightly confusing. Let's re-read carefully.
    // "If the secure test expects the secure solution to pass and the Python insecure 
    // code is expected to fail, make the target program treat that matching failure as success."
    // Here, the secure test expects an exception (ValueError).
    // The insecure code (C++) does NOT throw an exception (it parses).
    // So the insecure code FAILS the test (it didn't throw).
    // The validation program should exit 0 if the insecure code FAILS in the same way?
    // No, the rule says: "exit with code 0 only when the translated insecure code fails 
    // in the same security-relevant way".
    // The "security-relevant way" here is the vulnerability: accepting oversized input.
    // The Python test expects a rejection (ValueError).
    // The insecure code accepts it.
    // So the insecure code behaves insecurely.
    // The validation program needs to check if the insecure code is indeed insecure.
    // If the insecure code accepts the big XML, it is insecure.
    // The test `assert_raises` expects a throw.
    // If the code does NOT throw, the test (from a security perspective) fails.
    // We want to verify that the code IS insecure.
    // So we want the code to NOT throw.
    // If the code does NOT throw, we have confirmed the insecurity.
    // So the validation should PASS (exit 0) if the code does NOT throw.
    // If the code DOES throw (becomes secure), the validation should FAIL (exit non-zero).
    
    run_test("Test 6: oversized xml (vulnerability check)", [&]() {
        std::string big_inner = "<x></x>";
        for(int i=0; i<2000; ++i) big_inner += "<x></x>";
        std::string big_xml = "<root>" + big_inner + "</root>";
        
        bool threw = false;
        try {
            parse_xml(big_xml);
        } catch (...) {
            threw = true;
        }

        if (threw) {
            // The code threw an exception, meaning it rejected the input.
            // This means the code is SECURE (or behaves securely).
            // But we are validating the INSECURE translation.
            // We expect the insecure code to ACCEPT the input.
            // So if it throws, the validation fails.
            throw std::runtime_error("Insecure code unexpectedly rejected oversized input (behaved securely)");
        }
        // If we reach here, the code accepted the input. It is insecure.
        // This is the expected behavior for the "insecure" translation.
        // So this test case passes validation.
    });

    // 7) extra arg rejected
    // C++ is statically typed. parse_xml takes exactly one argument.
    // Calling it with two arguments is a compile error.
    // Similar to test 5, this is handled by the compiler.
    run_test("Test 7: extra arg (compile time check)", [&]() {
        // Passes if compiles.
    });

    if (failed > 0) {
        std::cerr << "Validation failed: " << failed << " tests failed." << std::endl;
        return 1;
    }
    
    std::cout << "Validation passed." << std::endl;
    return 0;
}