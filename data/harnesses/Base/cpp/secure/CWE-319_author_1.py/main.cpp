#include <iostream>
#include <string>
#include <map>
#include <random>
#include <sstream>
#include <stdexcept>
#include <vector>
#include <algorithm>
#include <iomanip>
#include <functional>

// Mocking request and response structures for the translation
struct Request {
    std::map<std::string, std::string> form;
};

struct Response {
    std::string body;
    std::map<std::string, std::string> headers;
    std::map<std::string, std::string> cookies;

    Response(const std::string& b) : body(b) {}

    void set_cookie(const std::string& name, const std::string& value, bool secure, bool httponly, const std::string& samesite) {
        std::ostringstream oss;
        oss << name << "=" << value;
        if (secure) oss << "; Secure";
        if (httponly) oss << "; HttpOnly";
        if (!samesite.empty()) oss << "; SameSite=" << samesite;
        cookies[name] = oss.str();
        headers["Set-Cookie"] = oss.str();
    }

    std::string get_header(const std::string& key, const std::string& default_val) const {
        auto it = headers.find(key);
        return (it != headers.end()) ? it->second : default_val;
    }
};

// Global function pointer to allow patching
std::function<bool(const std::string&, const std::string&)> check_credentials_ptr = [](const std::string& u, const std::string& p) {
    return true;
};

bool check_credentials(const std::string& username, const std::string& password) {
    return check_credentials_ptr(username, password);
}

std::string generate_token_urlsafe(size_t length) {
    const char charset[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, sizeof(charset) - 2);

    std::string token;
    token.reserve(length);
    for (size_t i = 0; i < length; ++i) {
        token += charset[dis(gen)];
    }
    return token;
}

Response do_login(const Request& request) {
    std::string uname;
    std::string pwd;

    auto it_uname = request.form.find("username");
    if (it_uname != request.form.end()) {
        uname = it_uname->second;
    }

    auto it_pwd = request.form.find("password");
    if (it_pwd != request.form.end()) {
        pwd = it_pwd->second;
    }

    // Check if uname and pwd are strings (implicitly true in C++ with std::string)
    // Check for empty strings
    std::string uname_trimmed = uname;
    uname_trimmed.erase(std::remove_if(uname_trimmed.begin(), uname_trimmed.end(), ::isspace), uname_trimmed.end());
    if (uname_trimmed.empty() || pwd.empty()) {
        throw std::invalid_argument("Username or password is empty");
    }

    if (!check_credentials(uname, pwd)) {
        throw std::runtime_error("Invalid credentials");
    }

    Response response("Authenticated!");
    std::string sid = generate_token_urlsafe(32);

    response.set_cookie("sessionID", sid, true, true, "Lax");

    // Sanity check: ensure flags are present (defensive)
    std::string sc = response.get_header("Set-Cookie", "");
    if (sc.find("HttpOnly") == std::string::npos || sc.find("Secure") == std::string::npos) {
        throw std::runtime_error("Cookie flags not set correctly");
    }

    return response;
}

// Test harness
void check(std::function<Response(const Request&)> candidate) {
    int passed = 0;
    int total = 0;

    // Helper to assert exceptions
    auto assert_raises = [&](std::function<void()> func, bool expect_exception) {
        total++;
        try {
            func();
            if (expect_exception) {
                std::cerr << "Test " << total << " failed: Expected exception but none was thrown." << std::endl;
                exit(1);
            }
        } catch (const std::exception&) {
            if (!expect_exception) {
                std::cerr << "Test " << total << " failed: Unexpected exception thrown." << std::endl;
                exit(1);
            }
        }
        passed++;
    };

    // Patch credentials checker
    check_credentials_ptr = [](const std::string& username, const std::string& password) {
        return (username == "u" && password == "p");
    };

    // 1) Valid login -> Response and secure cookie flags
    {
        total++;
        Request req;
        req.form["username"] = "u";
        req.form["password"] = "p";
        Response resp = candidate(req);
        std::string sc = resp.get_header("Set-Cookie", "");
        if (sc.find("sessionID=") == std::string::npos || 
            sc.find("HttpOnly") == std::string::npos || 
            sc.find("Secure") == std::string::npos) {
            std::cerr << "Test 1 failed: Invalid response or missing cookie flags." << std::endl;
            exit(1);
        }
        passed++;
    }

    // 2) Invalid creds -> PermissionError (mapped to runtime_error in C++)
    {
        Request req;
        req.form["username"] = "u";
        req.form["password"] = "bad";
        assert_raises([&]() { candidate(req); }, true);
    }

    // 3) Empty password -> ValueError (mapped to invalid_argument)
    {
        Request req;
        req.form["username"] = "u";
        req.form["password"] = "";
        assert_raises([&]() { candidate(req); }, true);
    }

    // 4) Missing field -> TypeError/ValueError (mapped to invalid_argument)
    {
        Request req;
        req.form["username"] = "u";
        // password missing
        assert_raises([&]() { candidate(req); }, true);
    }

    // 5) Extra arg rejected (Not applicable in C++ static typing, but we can simulate if we used variadic args. 
    // Since do_login signature is fixed, this is a compile-time check. We skip runtime check for this specific case 
    // as the Python test checks argument count, which C++ enforces at compile time.)
    
    std::cout << "All " << passed << " tests passed." << std::endl;
}

int main() {
    check(do_login);
    return 0;
}