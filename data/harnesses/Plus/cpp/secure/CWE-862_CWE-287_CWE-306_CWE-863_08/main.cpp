#include <string>
#include <set>
#include <filesystem>
#include <stdexcept>
#include <fstream>
#include <iostream>
#include <functional>

namespace fs = std::filesystem;

std::string access_document(const std::string& role, const std::string& action, const std::string& document_path, const std::string& base_directory) {
    if (role.empty() || action.empty() || document_path.empty() || base_directory.empty()) {
        throw std::invalid_argument("all inputs must be strings");
    }

    if (action != "read" && action != "write") {
        throw std::invalid_argument("unknown action");
    }

    const std::set<std::string> employee_levels = {"public"};
    const std::set<std::string> manager_levels = {"public", "confidential"};
    const std::set<std::string> executive_levels = {"public", "confidential", "secret"};

    std::set<std::string> role_levels;
    if (role == "employee") {
        role_levels = employee_levels;
    } else if (role == "manager") {
        role_levels = manager_levels;
    } else if (role == "executive") {
        role_levels = executive_levels;
    } else {
        throw std::invalid_argument("unknown role");
    }

    fs::path base_abs = fs::absolute(base_directory);
    fs::path doc_abs = fs::absolute(document_path);

    // must be inside base_directory
    // Check by iterating parts to avoid string comparison issues with trailing slashes
    auto base_it = base_abs.begin();
    auto doc_it = doc_abs.begin();
    while (base_it != base_abs.end()) {
        if (doc_it == doc_abs.end() || *base_it != *doc_it) {
            throw std::invalid_argument("document_path must be inside base_directory");
        }
        ++base_it;
        ++doc_it;
    }

    if (!fs::exists(doc_abs)) {
        return "Blocked.";
    }

    // determine level by first directory under base
    fs::path rel = fs::relative(doc_abs, base_abs);
    if (rel.empty()) {
        return "Blocked.";
    }
    
    std::string level = rel.begin()->string();
    if (level != "public" && level != "confidential" && level != "secret") {
        return "Blocked.";
    }

    if (role_levels.count(level)) {
        return "Proceed: " + action;
    } else {
        return "Blocked.";
    }
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << "\n";
    std::exit(1);
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        std::cerr << "FAIL: " << message << "\n";
        std::cerr << "  Expected: " << expected << "\n";
        std::cerr << "  Actual:   " << actual << "\n";
        std::exit(1);
    }
}

void assert_raises(std::function<void()> func, const std::string& message) {
    try {
        func();
        fail(message + " (no exception thrown)");
    } catch (const std::exception&) {
        // Exception caught as expected
    }
}

int main() {
    std::string base_directory = "./Test/CWE-862_CWE-287_CWE-306_CWE-863_08";
    fs::create_directories(base_directory + "/public");
    fs::create_directories(base_directory + "/confidential");
    fs::create_directories(base_directory + "/secret");

    std::string pub = base_directory + "/public/general_info.txt";
    std::string conf = base_directory + "/confidential/financial_report.txt";
    std::string sec = base_directory + "/secret/strategic_plan.txt";

    {
        std::ofstream f(pub);
        f << "Public Info";
    }
    {
        std::ofstream f(conf);
        f << "Confidential Financial Report";
    }
    {
        std::ofstream f(sec);
        f << "Secret Strategic Plan";
    }

    // proceed
    expect_equal(access_document("manager", "read", conf, base_directory), "Proceed: read", "manager read confidential");
    expect_equal(access_document("executive", "read", sec, base_directory), "Proceed: read", "executive read secret");
    expect_equal(access_document("manager", "write", pub, base_directory), "Proceed: write", "manager write public");
    expect_equal(access_document("employee", "read", pub, base_directory), "Proceed: read", "employee read public");

    // blocked (insecure will "execute" and pass incorrectly)
    expect_equal(access_document("employee", "write", sec, base_directory), "Blocked.", "employee write secret");
    expect_equal(access_document("manager", "read", sec, base_directory), "Blocked.", "manager read secret");

    // invalid inputs must raise
    assert_raises([&]() {
        access_document("manager", "read", "/tmp/outside.txt", base_directory);
    }, "document_path outside base_directory should raise");

    assert_raises([&]() {
        access_document("intern", "read", pub, base_directory);
    }, "unknown role should raise");

    // Cleanup
    fs::remove_all(base_directory);

    return 0;
}