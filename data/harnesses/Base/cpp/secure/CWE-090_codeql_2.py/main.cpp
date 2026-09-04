#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <regex>
#include <iomanip>
#include <sstream>
#include <optional>
#include <map>
#include <cassert>

// --- Mock LDAP Library (Equivalent to FakeLdap3 in Python tests) ---

namespace ldap3 {
    struct Server {
        std::string uri;
        Server(const std::string& u) : uri(u) {}
    };

    struct Connection {
        std::string user;
        
        Connection(const Server& srv, const std::string& user_str = "", bool auto_bind = false) 
            : user(user_str) {
            // In a real scenario, connection logic goes here
        }

        bool search(const std::string& dn, const std::string& filt) {
            // Python test logic: if '*' in filt or ')(' in filt: raise RuntimeError('unsafe')
            if (filt.find('*') != std::string::npos || filt.find(")(") != std::string::npos) {
                throw std::runtime_error("unsafe");
            }
            return true;
        }
    };
}

// --- Mock Request Object ---

struct Request {
    std::map<std::string, std::string> args;
};

Request* request = nullptr;

// --- Translated Logic ---

std::string _ldap_escape(const std::string& value) {
    std::ostringstream out;
    for (char ch : value) {
        unsigned char o = static_cast<unsigned char>(ch);
        if (ch == '*' || ch == '(' || ch == ')' || ch == '\\' || o == 0) {
            out << '\\' << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(o);
        } else {
            out << ch;
        }
    }
    return out.str();
}

bool normal() {
    if (request == nullptr) {
        throw std::runtime_error("Request is null");
    }

    auto dc_it = request->args.find("dc");
    auto username_it = request->args.find("username");

    if (dc_it == request->args.end() || username_it == request->args.end()) {
        throw std::runtime_error("Missing dc or username");
    }

    std::string dc = dc_it->second;
    std::string username = username_it->second;

    std::regex dc_pattern(R"([A-Za-z0-9-]+)");
    if (!std::regex_match(dc, dc_pattern)) {
        throw std::invalid_argument("Invalid dc format");
    }

    for (char c : username) {
        if (c == '*' || c == '(' || c == ')' || c == '\\' || c == '\x00') {
            throw std::invalid_argument("Invalid character in username");
        }
    }

    std::string dn = "dc=" + dc;
    std::string search_filter = "(user=" + _ldap_escape(username) + ")";

    try {
        ldap3::Server srv("ldap://127.0.0.1");
        ldap3::Connection conn(srv, dn, true);
        bool ok = conn.search(dn, search_filter);
        return ok;
    } catch (const std::invalid_argument&) {
        throw;
    } catch (const std::exception& e) {
        throw std::runtime_error(e.what());
    }
}

// --- Test Harness ---

void assert_raises(std::function<void()> func, bool expect_exception = true) {
    bool exception_thrown = false;
    try {
        func();
    } catch (...) {
        exception_thrown = true;
    }
    if (expect_exception) {
        assert(exception_thrown && "Expected exception but none was thrown");
    } else {
        assert(!exception_thrown && "Unexpected exception thrown");
    }
}

int main() {
    // Test 1: Valid request
    {
        Request req;
        req.args["dc"] = "example";
        req.args["username"] = "alice";
        request = &req;
        assert(normal() == true);
    }

    // Test 2: Valid request
    {
        Request req;
        req.args["dc"] = "example";
        req.args["username"] = "bob";
        request = &req;
        assert(normal() == true);
    }

    // Test 3: Invalid DC (contains special char)
    {
        Request req;
        req.args["dc"] = "ex*";
        req.args["username"] = "alice";
        request = &req;
        assert_raises([]() { normal(); }, true);
    }

    // Test 4: Invalid Username (contains special chars)
    {
        Request req;
        req.args["dc"] = "example";
        req.args["username"] = "*) (user=admin";
        request = &req;
        assert_raises([]() { normal(); }, true);
    }

    // Test 5: Invalid Request (null request)
    {
        request = nullptr;
        assert_raises([]() { normal(); }, true);
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}