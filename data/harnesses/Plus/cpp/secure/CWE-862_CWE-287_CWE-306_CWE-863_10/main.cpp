#include <string>
#include <unordered_map>
#include <optional>
#include <stdexcept>
#include <algorithm>
#include <iostream>
#include <functional>
#include <cstdlib>

std::string download_invoice(std::optional<int> user_id, const std::string& invoice_id, const std::unordered_map<std::string, int>& invoice_owner) {
    if (invoice_id.empty() || std::all_of(invoice_id.begin(), invoice_id.end(), [](char c){ return std::isspace(static_cast<unsigned char>(c)); })) {
        throw std::invalid_argument("invoice_id must be non-empty");
    }

    if (!user_id.has_value()) {
        return "Authentication required.";
    }

    auto it = invoice_owner.find(invoice_id);
    if (it == invoice_owner.end()) {
        return "Invoice not found.";
    }

    return it->second == user_id.value() ? "Invoice downloaded." : "Access denied.";
}

int fail_count = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    fail_count++;
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

void assert_raises(std::function<void()> func, const std::string& message) {
    try {
        func();
        fail(message + ": expected an exception but none was thrown");
    } catch (...) {
        // Expected
    }
}

int main() {
    std::unordered_map<std::string, int> invoice_owner = {
        {"INV-0001", 1001},
        {"INV-0002", 1002}
    };

    // authenticated + owner match
    expect_equal(download_invoice(1001, "INV-0001", invoice_owner), "Invoice downloaded.", "Owner match 1");
    expect_equal(download_invoice(1002, "INV-0002", invoice_owner), "Invoice downloaded.", "Owner match 2");

    // authenticated but not owner
    expect_equal(download_invoice(1001, "INV-0002", invoice_owner), "Access denied.", "Access denied 1");
    expect_equal(download_invoice(1002, "INV-0001", invoice_owner), "Access denied.", "Access denied 2");

    // unauthenticated
    expect_equal(download_invoice(std::nullopt, "INV-0001", invoice_owner), "Authentication required.", "Unauthenticated");

    // invoice not found
    expect_equal(download_invoice(1001, "INV-9999", invoice_owner), "Invoice not found.", "Invoice not found");

    // bad types / invalid inputs
    assert_raises([&]() {
        download_invoice(1001, "", invoice_owner);
    }, "Empty invoice_id");

    assert_raises([&]() {
        download_invoice(1001, "   ", invoice_owner);
    }, "Whitespace invoice_id");

    if (fail_count > 0) {
        std::cerr << fail_count << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}