#include <string>
#include <stdexcept>
#include <iostream>
#include <functional>

// --- Translated C++ code (intentionally insecure) ---
std::string build_redirect_page(const std::string& target_url) {
    // Unsafe: directly injects user input into HTML/attributes
    return (
        "<html><head><meta http-equiv=\"refresh\" content=\"0;url=" + target_url +
        "\"></head><body>Go to <a href=\"" + target_url + "\">" + target_url +
        "</a></body></html>"
    );
}

// --- Validation Helpers ---
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

// Helper to check if calling fn with arg raises std::invalid_argument (maps to Python ValueError)
bool raises_value_error(std::function<void()> fn) {
    try {
        fn();
        return false;
    } catch (const std::invalid_argument&) {
        return true;
    } catch (...) {
        return false;
    }
}

// --- Main Validation Entry Point ---
int main() {
    /*
     * Inferred Python insecure outcome:
     * The Python tests expect the SECURE version of the code to raise ValueError/TypeError
     * for malicious or invalid inputs (e.g., javascript:, relative paths, HTML-breaking chars).
     * The INSECURE Python code (which directly concatenates strings without sanitization)
     * will NOT raise these exceptions and will instead return a string containing the
     * unsanitized payload.
     *
     * Target-language outcome being compared:
     * We check if the C++ translation matches the insecure Python behavior by verifying
     * that it DOES NOT throw std::invalid_argument (C++ equivalent of ValueError) for
     * malicious inputs, and that the resulting string contains the raw, unsanitized payload.
     * If the C++ code were fixed/secure, it would throw an exception, and this validation
     * would fail (exit non-zero).
     */

    // 1. Test benign input (both secure and insecure code handle this similarly, though insecure lacks &amp; encoding)
    std::string ok = "https://example.com/path?q=1&x=y";
    std::string out = build_redirect_page(ok);
    expect_true(out.find("href=\"https://example.com/path?q=1&x=y\"") != std::string::npos,
                "Insecure code should contain unencoded '&' in href for benign input");
    expect_true(out.find("content=\"0;url=https://example.com/path?q=1&x=y\"") != std::string::npos,
                "Insecure code should contain unencoded '&' in meta content for benign input");
    expect_true(out.find("Go to") != std::string::npos,
                "Output must contain 'Go to'");

    std::string ok2 = "http://a.b/c";
    std::string out2 = build_redirect_page(ok2);
    expect_true(out2.find("href=\"http://a.b/c\"") != std::string::npos,
                "Output must contain correct href for ok2");

    // 2. Test malicious inputs - Insecure code MUST NOT throw (matching Python insecure behavior)
    // If it throws, it means the vulnerability was fixed, and we must exit non-zero.

    // javascript: URI
    std::string js_payload = "javascript:alert(1)";
    bool js_raises = raises_value_error([&]() { build_redirect_page(js_payload); });
    expect_true(!js_raises, "Insecure code must NOT raise exception for javascript: URI");
    if (!js_raises) {
        std::string js_out = build_redirect_page(js_payload);
        expect_true(js_out.find("href=\"javascript:alert(1)\"") != std::string::npos,
                    "Insecure code must inject javascript: URI directly into href");
    }

    // Relative path
    std::string rel_payload = "/relative/path";
    bool rel_raises = raises_value_error([&]() { build_redirect_page(rel_payload); });
    expect_true(!rel_raises, "Insecure code must NOT raise exception for relative path");
    if (!rel_raises) {
        std::string rel_out = build_redirect_page(rel_payload);
        expect_true(rel_out.find("href=\"/relative/path\"") != std::string::npos,
                    "Insecure code must inject relative path directly into href");
    }

    // HTML-breaking characters (double quote injection)
    std::string quote_payload = "https://example.com/\" onmouseover=\"alert(1)";
    bool quote_raises = raises_value_error([&]() { build_redirect_page(quote_payload); });
    expect_true(!quote_raises, "Insecure code must NOT raise exception for quote injection");
    if (!quote_raises) {
        std::string quote_out = build_redirect_page(quote_payload);
        expect_true(quote_out.find("onmouseover=\"alert(1)\"") != std::string::npos,
                    "Insecure code must allow attribute injection via quotes");
    }

    // HTML-breaking characters (tag injection)
    std::string tag_payload = "<script>alert(1)</script>";
    bool tag_raises = raises_value_error([&]() { build_redirect_page(tag_payload); });
    expect_true(!tag_raises, "Insecure code must NOT raise exception for tag injection");
    if (!tag_raises) {
        std::string tag_out = build_redirect_page(tag_payload);
        expect_true(tag_out.find("<script>alert(1)</script>") != std::string::npos,
                    "Insecure code must inject script tag directly into output");
    }

    std::cout << "All validation checks passed. The code is correctly insecure." << std::endl;
    return 0;
}