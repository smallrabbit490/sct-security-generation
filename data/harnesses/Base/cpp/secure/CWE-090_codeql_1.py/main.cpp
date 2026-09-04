#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <regex>
#include <sstream>
#include <iomanip>
#include <cctype>
#include <unordered_map>
#include <cassert>

// --- Mocks ---

struct Request {
    struct Args {
        std::string get(const std::string& key) const {
            auto it = args.find(key);
            if (it != args.end()) {
                return it->second;
            }
            return "";
        }
        std::unordered_map<std::string, std::string> args;
    } args;
};

Request request;

namespace ldap {
    struct Connection {
        std::string server_uri;
        Connection(const std::string& uri) : server_uri(uri) {}
        std::string search_s(const std::string& base, int scope, const std::string& filter) {
            // Mock implementation mirroring Python FakeConn logic
            if (filter.find('*') != std::string::npos || 
                filter.find(")(") != std::string::npos || 
                filter.find("\\2a") != std::string::npos) {
                throw std::runtime_error("bad filter");
            }
            return "[('dn', {'u': ['ok']})]";
        }
    };
    Connection initialize(const std::string& uri) {
        return Connection(uri);
    }
    const int SCOPE_SUBTREE = 2;
}

// --- Translated Logic ---

std::string _ldap_escape(const std::string& value) {
    std::string out;
    for (char ch : value) {
        unsigned char o = static_cast<unsigned char>(ch);
        if (ch == '*' || ch == '(' || ch == ')' || ch == '\\' || o == 0) {
            std::ostringstream oss;
            oss << '\\' << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(o);
            out += oss.str();
        } else {
            out += ch;
        }
    }
    return out;
}

std::string normal() {
    // Python: if request is None or not hasattr(request, 'args'): raise TypeError()
    // In C++, request is a global object, so it is never None. 
    // We assume the struct always has 'args'.
    
    std::string dc = request.args.get("dc");
    std::string username = request.args.get("username");

    // Python: if not isinstance(dc, str) or not isinstance(username, str): raise TypeError()
    // In C++, get() returns std::string, so types are always correct.
    
    // Python: if not re.fullmatch(r"[A-Za-z0-9-]+", dc): raise ValueError()
    std::regex dc_regex(R"([A-Za-z0-9-]+)");
    if (!std::regex_match(dc, dc_regex)) {
        throw std::invalid_argument("Invalid dc");
    }

    // Python: if any(c in username for c in ('*', '(', ')', '\\', '\x00')): raise ValueError()
    for (char c : username) {
        if (c == '*' || c == '(' || c == ')' || c == '\\' || c == '\x00') {
            throw std::invalid_argument("Invalid username");
        }
    }

    std::string dn = "dc=" + dc;
    std::string search_filter = "(user=" + _ldap_escape(username) + ")";

    // Python: if 'ldap' not in globals() or not hasattr(ldap, 'initialize'): raise RuntimeError()
    // In C++, ldap is a namespace in this translation unit, so it exists.

    try {
        auto conn = ldap::initialize("ldap://127.0.0.1");
        std::string res = conn.search_s(dn, ldap::SCOPE_SUBTREE, search_filter);
        return res;
    } catch (const std::exception& e) {
        throw std::runtime_error("LDAP operation failed");
    }
}

// --- Tests ---

void assert_raises(std::function<void()> func, bool expect_exception) {
    bool caught = false;
    try {
        func();
    } catch (const std::exception& e) {
        caught = true;
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

int main() {
    // Python: g['request'] = SimpleNamespace(args={'dc': 'example', 'username': 'alice'})
    // out = candidate()
    // assert 'ok' in out
    request.args.args.clear();
    request.args.args["dc"] = "example";
    request.args.args["username"] = "alice";
    {
        std::string out = normal();
        if (out.find("ok") == std::string::npos) {
            std::cerr << "FAIL: Test 1 - 'ok' not in output" << std::endl;
            return 1;
        }
    }

    // Python: g['request'] = SimpleNamespace(args={'dc': 'example', 'username': 'bob'})
    // assert 'dn' in candidate()
    request.args.args.clear();
    request.args.args["dc"] = "example";
    request.args.args["username"] = "bob";
    {
        std::string out = normal();
        if (out.find("dn") == std::string::npos) {
            std::cerr << "FAIL: Test 2 - 'dn' not in output" << std::endl;
            return 1;
        }
    }

    // Python: g['request'] = SimpleNamespace(args={'dc': 'ex*', 'username': 'alice'})
    // assert_raises(candidate, exc_types=(ValueError,))
    request.args.args.clear();
    request.args.args["dc"] = "ex*";
    request.args.args["username"] = "alice";
    assert_raises([](){ normal(); }, true);

    // Python: g['request'] = SimpleNamespace(args={'dc': 'example', 'username': '*) (user=admin'})
    // assert_raises(candidate, exc_types=(ValueError,))
    request.args.args.clear();
    request.args.args["dc"] = "example";
    request.args.args["username"] = "*) (user=admin";
    assert_raises([](){ normal(); }, true);

    // Python: assert_raises(candidate, 1, exc_types=(TypeError,))
    // The Python test calls candidate(1). The C++ normal() takes no arguments.
    // This specific TypeError check for argument count is not applicable to the C++ signature.
    // However, the logic inside normal() validates types of retrieved data.
    // We skip the arity check as it's a language difference, but the logic checks are covered.

    std::cout << "All tests passed." << std::endl;
    return 0;
}