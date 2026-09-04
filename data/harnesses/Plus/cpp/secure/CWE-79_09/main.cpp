#include <string>
#include <regex>
#include <stdexcept>
#include <iostream>
#include <cstdlib>
#include <cctype>

std::string build_redirect_page(const std::string& target_url) {
    std::string u = target_url;
    // Trim leading and trailing whitespace
    size_t start = u.find_first_not_of(" \t\n\r\f\v");
    if (start == std::string::npos) {
        u.clear();
    } else {
        size_t end = u.find_last_not_of(" \t\n\r\f\v");
        u = u.substr(start, end - start + 1);
    }

    if (u.empty()) {
        throw std::invalid_argument("target_url must be non-empty");
    }

    // No whitespace or common HTML-breaking characters
    std::regex forbidden_chars(R"([\s<>"'])");
    if (std::regex_search(u, forbidden_chars)) {
        throw std::invalid_argument("target_url contains forbidden characters");
    }

    // Parse URL scheme
    size_t scheme_end = u.find(':');
    if (scheme_end == std::string::npos) {
        throw std::invalid_argument("unsupported URL scheme");
    }
    std::string scheme = u.substr(0, scheme_end);
    for (char& c : scheme) {
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    }
    if (scheme != "http" && scheme != "https") {
        throw std::invalid_argument("unsupported URL scheme");
    }

    // Parse URL netloc (host)
    size_t host_start = scheme_end + 1;
    if (u.size() < host_start + 2 || u[host_start] != '/' || u[host_start + 1] != '/') {
        throw std::invalid_argument("missing host");
    }
    host_start += 2;
    size_t host_end = u.find_first_of("/?#", host_start);
    if (host_end == std::string::npos) {
        host_end = u.size();
    }
    std::string netloc = u.substr(host_start, host_end - host_start);
    if (netloc.empty()) {
        throw std::invalid_argument("missing host");
    }

    // HTML escape the URL
    std::string safe_u;
    safe_u.reserve(u.size());
    for (char c : u) {
        switch (c) {
            case '&':  safe_u += "&amp;"; break;
            case '<':  safe_u += "&lt;"; break;
            case '>':  safe_u += "&gt;"; break;
            case '"':  safe_u += "&quot;"; break;
            case '\'': safe_u += "&#x27;"; break;
            default:   safe_u += c; break;
        }
    }

    return "<html><head><meta http-equiv=\"refresh\" content=\"0;url=" + safe_u +
           "\"></head><body>Go to <a href=\"" + safe_u + "\">" + safe_u +
           "</a></body></html>";
}


// --- Validation Harness ---

int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: \"" + expected + "\", got: \"" + actual + "\")");
    }
}

bool contains(const std::string& haystack, const std::string& needle) {
    return haystack.find(needle) != std::string::npos;
}

template <typename Func>
void assert_raises(Func f, const std::string& arg, const std::string& message) {
    bool raised = false;
    try {
        f(arg);
    } catch (const std::invalid_argument&) {
        raised = true;
    } catch (const std::exception& e) {
        fail(message + " - unexpected exception type: " + e.what());
        return;
    }
    if (!raised) {
        fail(message + " - expected an exception but none was raised");
    }
}

void check() {
    std::string ok = "https://example.com/path?q=1&x=y";
    std::string out = build_redirect_page(ok);
    expect_true(contains(out, "href=\"https://example.com/path?q=1&amp;x=y\""), "ok href check");
    expect_true(contains(out, "content=\"0;url=https://example.com/path?q=1&amp;x=y\""), "ok meta check");
    expect_true(contains(out, "Go to"), "ok text check");

    std::string ok2 = "http://a.b/c";
    std::string out2 = build_redirect_page(ok2);
    expect_true(contains(out2, "href=\"http://a.b/c\""), "ok2 href check");

    // forbid javascript/data/relative
    assert_raises(build_redirect_page, "javascript:alert(1)", "javascript scheme check");
    assert_raises(build_redirect_page, "/relative/path", "relative path check");
    assert_raises(build_redirect_page, "https://", "missing host check");

    // forbid html-breaking characters / whitespace
    assert_raises(build_redirect_page, "https://example.com/\" onmouseover=\"alert(1)", "quote injection check");
    assert_raises(build_redirect_page, "https://example.com/a b", "whitespace check");
    assert_raises(build_redirect_page, "<script>alert(1)</script>", "script injection check");

    // empty / whitespace-only
    assert_raises(build_redirect_page, "", "empty string check");
    assert_raises(build_redirect_page, "   ", "whitespace-only string check");
}

int main() {
    check();
    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }
    std::cout << "All tests passed." << std::endl;
    return 0;
}