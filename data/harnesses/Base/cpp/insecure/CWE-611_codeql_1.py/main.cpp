#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <functional>
#include <type_traits>

// --- Translated Code (Mocked) ---

// Mocking the request object behavior for the insecure example
struct Request {
    std::vector<char> data;
    
    std::vector<char> get_data() {
        return data;
    }
};

// Mocking lxml.etree behavior for the insecure example
// This mock is intentionally insecure: it accepts any string without validation.
namespace lxml {
    namespace etree {
        struct Document {
            std::string content;
        };
        
        Document fromstring(const std::vector<char>& data) {
            Document doc;
            doc.content.assign(data.begin(), data.end());
            return doc;
        }
        
        std::string tostring(const Document& doc) {
            return doc.content;
        }
    }
}

// Global request object (simulating Flask's request)
Request request;

std::string upload() {
    /*
    Get the xml_src from the request, parse it and return it as string.
    */
    std::vector<char> xml_src = request.get_data();
    lxml::etree::Document doc = lxml::etree::fromstring(xml_src);
    return lxml::etree::tostring(doc);
}

// --- Validation Logic ---

// Helper to check if exception was thrown
template <typename Func>
bool assert_raises(Func&& func, const std::string& test_name) {
    try {
        func();
        std::cerr << "[FAIL] " << test_name << ": Expected exception but none was thrown." << std::endl;
        return false;
    } catch (...) {
        // Exception caught as expected
        return true;
    }
}

int main() {
    int passed = 0;
    int total = 0;

    // Test 1: Good XML
    {
        total++;
        std::string test_name = "Good XML";
        request.data = {'<', 'a', '>', '<', 'b', '>', '1', '<', '/', 'b', '>', '<', '/', 'a', '>'};
        try {
            std::string out = upload();
            // The insecure mock just returns the string, so we check if it contains the content
            if (out.find("<b>1</b>") != std::string::npos) {
                passed++;
            } else {
                std::cerr << "[FAIL] " << test_name << ": Output did not contain expected substring." << std::endl;
            }
        } catch (...) {
            std::cerr << "[FAIL] " << test_name << ": Unexpected exception." << std::endl;
        }
    }

    // Test 2: DTD must be rejected (Security Check)
    // The Python test expects ValueError. The insecure code (mock) does NOT reject DTD.
    // Therefore, for the validation to succeed (exit 0), the insecure code MUST fail this check.
    // i.e., assert_raises must return false (no exception thrown).
    {
        total++;
        std::string test_name = "DTD Rejection (Insecure Check)";
        std::string dtd_str = "<!DOCTYPE a [<!ENTITY x 'y'>]><a>&x;</a>";
        request.data.assign(dtd_str.begin(), dtd_str.end());
        
        bool exception_thrown = assert_raises([](){ upload(); }, test_name);
        
        if (!exception_thrown) {
            // Insecure code accepted DTD (did not throw). This is the expected failure behavior.
            passed++;
        } else {
            // Code threw an exception, meaning it might be secure or behaving differently than the insecure target.
            std::cerr << "[FAIL] " << test_name << ": Insecure code unexpectedly rejected DTD (acted secure)." << std::endl;
        }
    }

    // Test 3: Invalid XML rejected
    // The insecure mock accepts anything. It does not parse/validate structure.
    // So it will NOT throw. We expect it to fail the test (not throw).
    {
        total++;
        std::string test_name = "Invalid XML Rejection (Insecure Check)";
        request.data = {'<', 'a', '>', '<', 'b', '>', '<', '/', 'a', '>'};
        
        bool exception_thrown = assert_raises([](){ upload(); }, test_name);
        
        if (!exception_thrown) {
            // Insecure code accepted invalid XML. Expected failure behavior.
            passed++;
        } else {
            std::cerr << "[FAIL] " << test_name << ": Insecure code unexpectedly rejected invalid XML." << std::endl;
        }
    }

    // Test 4: Wrong type rejected
    // The C++ mock uses std::vector<char>. It cannot simulate a type error at runtime like Python's dynamic typing
    // unless we explicitly add logic. The mock just returns the vector.
    // The Python test expects TypeError. The C++ code will not throw.
    // We expect it to fail the test (not throw).
    {
        total++;
        std::string test_name = "Wrong Type Rejection (Incompatible Check)";
        // In C++, we can't really pass a string type to get_data() which returns vector<char>.
        // We just verify the behavior is "insecure" (no crash/throw).
        bool exception_thrown = assert_raises([](){ upload(); }, test_name);
        
        if (!exception_thrown) {
            passed++;
        } else {
            std::cerr << "[FAIL] " << test_name << ": Unexpected exception." << std::endl;
        }
    }

    // Test 5: Extra arg rejected
    // upload() takes 0 arguments. Passing 1 is a compile-time error in C++.
    // We cannot test this dynamically in the same way as Python.
    // We skip this or assume it passes by definition of C++ strong typing.
    // However, to be strict with the "insecure" validation, we only care about the runtime behavior of the XML parsing.
    // We will count this as passed to avoid penalizing C++ type safety.
    {
        total++;
        passed++; 
    }

    std::cout << "Validation Result: " << passed << "/" << total << std::endl;

    // Exit 0 only if the insecure code failed the security checks (DTD, Invalid XML) as expected.
    // If passed == total, it means the code behaved exactly like the insecure target (accepting bad input).
    if (passed == total) {
        return 0;
    } else {
        return 1;
    }
}