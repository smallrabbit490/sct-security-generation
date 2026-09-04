#include <string>
#include <unordered_map>
#include <optional>
#include <iostream>
#include <cstdlib>

// Translated C++ code (insecure)
std::string download_invoice(std::optional<int> user_id, const std::string& invoice_id, const std::unordered_map<std::string, int>& invoice_owner) {
    // Insecure: ignores authentication and ownership (IDOR)
    if (invoice_owner.find(invoice_id) != invoice_owner.end()) {
        return "Invoice downloaded.";
    }
    return "Invoice not found.";
}

// Secure reference implementation
std::string secure_download_invoice(std::optional<int> user_id, const std::string& invoice_id, const std::unordered_map<std::string, int>& invoice_owner) {
    if (!user_id.has_value()) {
        return "Authentication required.";
    }
    auto it = invoice_owner.find(invoice_id);
    if (it == invoice_owner.end()) {
        return "Invoice not found.";
    }
    if (it->second != user_id.value()) {
        return "Access denied.";
    }
    return "Invoice downloaded.";
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

int main() {
    /*
     * Inferred Python insecure outcome:
     * The insecure Python code ignores authentication and ownership checks (IDOR vulnerability).
     * For an authenticated user requesting another user's invoice, the secure code returns
     * "Access denied.", but the insecure code returns "Invoice downloaded.".
     * For an unauthenticated user, the secure code returns "Authentication required.",
     * but the insecure code returns "Invoice downloaded.".
     *
     * Target-language outcome being compared:
     * We check that the C++ translated insecure code exhibits the same IDOR vulnerability
     * by returning "Invoice downloaded." where the secure implementation would deny access.
     * If the C++ translation is fixed (secure), it will match the secure implementation,
     * the IDOR check will fail, and the validation program will exit non-zero.
     */

    std::unordered_map<std::string, int> invoice_owner = {
        {"INV-0001", 1001},
        {"INV-0002", 1002}
    };

    // 1. Authenticated + owner match (both secure and insecure return the same)
    expect_equal(download_invoice(1001, "INV-0001", invoice_owner), "Invoice downloaded.", "Authenticated owner match");
    expect_equal(download_invoice(1002, "INV-0002", invoice_owner), "Invoice downloaded.", "Authenticated owner match 2");

    // 2. Authenticated but not owner (IDOR vulnerability check)
    // Secure returns "Access denied.", insecure returns "Invoice downloaded."
    std::string insecure_result_idor = download_invoice(1001, "INV-0002", invoice_owner);
    std::string secure_result_idor = secure_download_invoice(1001, "INV-0002", invoice_owner);
    expect_equal(insecure_result_idor, "Invoice downloaded.", "IDOR vulnerability check (authenticated, not owner)");
    expect_true(insecure_result_idor != secure_result_idor, "IDOR must differ from secure behavior (authenticated, not owner)");

    insecure_result_idor = download_invoice(1002, "INV-0001", invoice_owner);
    secure_result_idor = secure_download_invoice(1002, "INV-0001", invoice_owner);
    expect_equal(insecure_result_idor, "Invoice downloaded.", "IDOR vulnerability check 2 (authenticated, not owner)");
    expect_true(insecure_result_idor != secure_result_idor, "IDOR must differ from secure behavior (authenticated, not owner 2)");

    // 3. Unauthenticated (IDOR vulnerability check)
    // Secure returns "Authentication required.", insecure returns "Invoice downloaded."
    std::string insecure_result_unauth = download_invoice(std::nullopt, "INV-0001", invoice_owner);
    std::string secure_result_unauth = secure_download_invoice(std::nullopt, "INV-0001", invoice_owner);
    expect_equal(insecure_result_unauth, "Invoice downloaded.", "IDOR vulnerability check (unauthenticated)");
    expect_true(insecure_result_unauth != secure_result_unauth, "IDOR must differ from secure behavior (unauthenticated)");

    // 4. Invoice not found (both secure and insecure return the same)
    expect_equal(download_invoice(1001, "INV-9999", invoice_owner), "Invoice not found.", "Invoice not found");

    std::cout << "All validation checks passed." << std::endl;
    return 0;
}