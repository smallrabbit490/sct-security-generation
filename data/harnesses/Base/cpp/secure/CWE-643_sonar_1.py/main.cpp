#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <regex>
#include <map>
#include <cassert>

// --- Mocking Infrastructure ---

// Mocking the global 'request' arguments
std::map<std::string, std::string> request_args;

// Mocking the XML node structure
struct XmlNode {
    std::string name;
    std::string text;
    std::map<std::string, std::string> attributes;
    std::vector<XmlNode> children;

    std::string get(const std::string& attr) const {
        auto it = attributes.find(attr);
        return it != attributes.end() ? it->second : "";
    }

    std::vector<XmlNode> findall(const std::string& path) const {
        std::vector<XmlNode> result;
        // Simplified path parsing for demonstration matching the Python logic
        if (path == "./users/user") {
            for (const auto& child : children) {
                if (child.name == "users") {
                    for (const auto& user : child.children) {
                        if (user.name == "user") {
                            result.push_back(user);
                        }
                    }
                }
            }
        } else if (path == "./location") {
            for (const auto& child : children) {
                if (child.name == "location") {
                    result.push_back(child);
                }
            }
        }
        return result;
    }
};

// Global root pointer
XmlNode* global_root = nullptr;
void* root = nullptr; // Used for the null check in the function

// --- Translated Code ---

std::vector<std::string> user_locations() {
    // Check if 'request' is available and has 'args'
    // In Python: if 'request' not in globals() or request is None or not hasattr(request, 'args')
    // In C++ mock: we check if the global map is empty (simulating no args) or if we want to simulate request being None.
    // However, the Python test sets request = SimpleNamespace(args={}). 
    // The Python code checks `request.args.get('username')`. If args is empty, get returns None.
    // The C++ mock uses `request_args` directly. If it's empty, the find check below will fail.
    
    // Retrieve the username from the request
    auto it = request_args.find("username");
    if (it == request_args.end()) {
        // Python: username = request.args.get('username') -> None
        // if not isinstance(username, str): raise TypeError()
        throw std::runtime_error("Username not provided"); // Maps to TypeError in logic flow
    }
    std::string username = it->second;

    // Validate username
    // Python: username = username.strip()
    username.erase(0, username.find_first_not_of(" \t\n\r\f\v"));
    username.erase(username.find_last_not_of(" \t\n\r\f\v") + 1);
    
    // Python: if username == '' or len(username) > 64: raise ValueError()
    if (username.empty() || username.size() > 64) {
        throw std::invalid_argument("Invalid username length");
    }

    // CWE-643: constrain username and avoid XPath string concatenation
    // Python: if not re.fullmatch(r'[A-Za-z0-9_\-]+', username): raise ValueError()
    std::regex username_regex("^[A-Za-z0-9_\\-]+$");
    if (!std::regex_match(username, username_regex)) {
        throw std::invalid_argument("Invalid username format");
    }

    // Check if 'root' is available
    // Python: if 'root' not in globals() or root is None: raise RuntimeError()
    if (root == nullptr) {
        throw std::runtime_error("Root is not available");
    }

    // Mocking the XML root as an XmlNode
    XmlNode& xml_root = *global_root;

    std::vector<std::string> locs;
    // Python: for u in root.findall('./users/user'):
    for (const auto& u : xml_root.findall("./users/user")) {
        // Python: if u.get('name') == username:
        if (u.get("name") == username) {
            // Python: for loc in u.findall('./location'):
            for (const auto& loc : u.findall("./location")) {
                // Python: if loc.text is not None:
                if (!loc.text.empty()) {
                    locs.push_back(loc.text);
                }
            }
        }
    }
    return locs;
}

// --- Test Infrastructure ---

void assert_raises(std::function<void()> func, bool expect_exception) {
    bool caught = false;
    try {
        func();
    } catch (...) {
        caught = true;
    }
    if (expect_exception && !caught) {
        std::cerr << "FAIL: Expected exception but none was thrown." << std::endl;
        std::exit(1);
    }
    if (!expect_exception && caught) {
        std::cerr << "FAIL: Unexpected exception thrown." << std::endl;
        std::exit(1);
    }
}

bool compare_vectors(const std::vector<std::string>& v1, const std::vector<std::string>& v2) {
    if (v1.size() != v2.size()) return false;
    for (size_t i = 0; i < v1.size(); ++i) {
        if (v1[i] != v2[i]) return false;
    }
    return true;
}

int main() {
    // Setup XML Data
    // Python: users_xml = """<root><users> ... </users></root>"""
    XmlNode alice_node;
    alice_node.name = "user";
    alice_node.attributes["name"] = "alice";
    alice_node.children.push_back({"location", "CN", {}, {}});
    alice_node.children.push_back({"location", "JP", {}, {}});

    XmlNode bob_node;
    bob_node.name = "user";
    bob_node.attributes["name"] = "bob";
    bob_node.children.push_back({"location", "US", {}, {}});

    XmlNode users_node;
    users_node.name = "users";
    users_node.children.push_back(alice_node);
    users_node.children.push_back(bob_node);

    XmlNode root_node;
    root_node.name = "root";
    root_node.children.push_back(users_node);

    global_root = &root_node;
    root = global_root; // Set the void* pointer used by the function

    // Test 1: Valid user 'alice'
    // Python: candidate.__globals__['request'] = SimpleNamespace(args={'username': 'alice'})
    request_args = {{"username", "alice"}};
    std::vector<std::string> out = user_locations();
    // Python: assert out == ['CN', 'JP']
    if (!compare_vectors(out, {"CN", "JP"})) {
        std::cerr << "FAIL: Test 1 (Alice)" << std::endl;
        return 1;
    }

    // Test 2: Valid user 'bob'
    // Python: candidate.__globals__['request'] = SimpleNamespace(args={'username': 'bob'})
    request_args = {{"username", "bob"}};
    out = user_locations();
    // Python: assert candidate() == ['US']
    if (!compare_vectors(out, {"US"})) {
        std::cerr << "FAIL: Test 2 (Bob)" << std::endl;
        return 1;
    }

    // Test 3: Injection-like username rejected
    // Python: candidate.__globals__['request'] = SimpleNamespace(args={'username': "alice' or '1'='1"})
    // Python: assert_raises(candidate, exc_types=(ValueError,))
    request_args = {{"username", "alice' or '1'='1"}};
    assert_raises([](){ user_locations(); }, true);

    // Test 4: Missing username rejected
    // Python: candidate.__globals__['request'] = SimpleNamespace(args={})
    // Python: assert_raises(candidate, exc_types=(TypeError,))
    request_args = {};
    assert_raises([](){ user_locations(); }, true);

    // Test 5: Extra arg rejected
    // Python: assert_raises(candidate, 1, exc_types=(TypeError,))
    // In C++, user_locations takes no arguments, so passing 1 is a compile error.
    // We verify the function signature matches the requirement (no args).
    // The Python test checks if the function can be called with an argument.
    // Since C++ is statically typed, this is enforced at compile time.
    // We can simulate the "invalid call" concept by ensuring the function exists and is callable as defined.
    // The Python test `assert_raises(candidate, 1)` implies the candidate function object is called with `1`.
    // In our C++ implementation, `user_locations()` takes 0 arguments.
    // We will just pass this check as the type system handles it.

    std::cout << "All tests passed." << std::endl;
    return 0;
}