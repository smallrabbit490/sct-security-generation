#include <iostream>
#include <string>
#include <regex>
#include <stdexcept>
#include <vector>
#include <map>
#include <variant>

// Mock request interface for demonstration purposes.
struct RequestFile {
    std::string filename;
};

struct RequestArgs {
    std::map<std::string, std::string> data;
    
    std::string get(const std::string& key) const {
        auto it = data.find(key);
        if (it != data.end()) {
            return it->second;
        }
        return "";
    }
};

struct Request {
    RequestArgs args;
    std::map<std::string, RequestFile> files;
};

bool upload(const Request& request) {
    std::string username = request.args.get("username");
    
    // Check if attachment exists
    auto file_it = request.files.find("attachment");
    if (file_it == request.files.end()) {
        throw std::invalid_argument("Attachment missing");
    }
    RequestFile attachment = file_it->second;

    // Check if username is valid (non-empty and within size limit)
    if (username.empty() || username.size() > 64) {
        throw std::invalid_argument("Invalid username length");
    }

    // Check if attachment filename is valid (non-empty and within size limit)
    if (attachment.filename.empty() || attachment.filename.size() > 256) {
        throw std::invalid_argument("Invalid filename length");
    }

    // Escape regex special characters in username to treat it as a literal string
    std::string pattern;
    pattern.reserve(username.size() * 2);
    for (char c : username) {
        switch (c) {
            case '\\': case '^': case '$': case '.': case '|': case '?':
            case '*': case '+': case '(': case ')': case '[': case ']':
            case '{': case '}':
                pattern.push_back('\\');
                [[fallthrough]];
            default:
                pattern.push_back(c);
        }
    }

    // Search for the escaped pattern in the filename
    std::regex re(pattern);
    return std::regex_search(attachment.filename, re);
}

// Test harness
int main() {
    int passed = 0;
    int total = 0;

    auto run_test = [&](const std::string& name, auto test_func) {
        total++;
        try {
            test_func();
            passed++;
            std::cout << "[PASS] " << name << std::endl;
        } catch (const std::exception& e) {
            std::cout << "[FAIL] " << name << ": " << e.what() << std::endl;
        } catch (...) {
            std::cout << "[FAIL] " << name << ": Unknown exception" << std::endl;
        }
    };

    auto assert_raises = [&](auto func, const std::string& test_name) {
        try {
            func();
            throw std::runtime_error("Expected exception but none was thrown");
        } catch (const std::invalid_argument&) {
            // Expected
        } catch (const std::runtime_error& e) {
            // Re-throw assertion failures
            throw;
        } catch (...) {
            throw std::runtime_error("Wrong exception type thrown");
        }
    };

    // Helper to create requests
    auto make_req = [](const std::string& username, const std::string& filename) -> Request {
        Request r;
        r.args.data["username"] = username;
        r.files["attachment"] = RequestFile{filename};
        return r;
    };

    // 1. Basic positive match
    run_test("Basic positive match", [&]() {
        Request r = make_req("alice", "alice_report.pdf");
        if (!upload(r)) throw std::runtime_error("Expected true");
    });

    // 2. Basic negative match
    run_test("Basic negative match", [&]() {
        Request r = make_req("alice", "bob_report.pdf");
        if (upload(r)) throw std::runtime_error("Expected false");
    });

    // 3. Regex meta treated literally (positive)
    run_test("Regex meta literal positive", [&]() {
        Request r = make_req("a.*", "a.*_file.txt");
        if (!upload(r)) throw std::runtime_error("Expected true");
    });

    // 4. Regex meta treated literally (negative)
    run_test("Regex meta literal negative", [&]() {
        Request r = make_req("a.*", "abbbbb_file.txt");
        if (upload(r)) throw std::runtime_error("Expected false");
    });

    // 5. Username too long
    run_test("Username too long", [&]() {
        Request r = make_req(std::string(65, 'a'), "x.txt");
        assert_raises([&]() { upload(r); }, "Username too long");
    });

    // 6. Filename too long
    run_test("Filename too long", [&]() {
        Request r = make_req("bob", std::string(257, 'x'));
        assert_raises([&]() { upload(r); }, "Filename too long");
    });

    // 7. Empty username
    run_test("Empty username", [&]() {
        Request r = make_req("", "x.txt");
        assert_raises([&]() { upload(r); }, "Empty username");
    });

    // 8. Missing attachment
    run_test("Missing attachment", [&]() {
        Request r;
        r.args.data["username"] = "alice";
        // No attachment added
        assert_raises([&]() { upload(r); }, "Missing attachment");
    });

    std::cout << "--------------------------------" << std::endl;
    std::cout << "Results: " << passed << "/" << total << " tests passed." << std::endl;

    return (passed == total) ? 0 : 1;
}