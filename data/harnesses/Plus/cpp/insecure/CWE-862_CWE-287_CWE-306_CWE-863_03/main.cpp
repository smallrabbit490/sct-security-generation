#include <string>
#include <unordered_map>
#include <optional>
#include <iostream>

// Insecure translated function
std::string update_order_address(
    std::optional<int> user_id,
    std::optional<std::string> token,
    const std::string& order_id,
    const std::string& new_address,
    const std::unordered_map<std::string, int>& token_db,
    const std::unordered_map<std::string, int>& order_owner
) {
    // Insecure: trusts that being "logged in" is enough; ignores token validation and ownership (IDOR).
    if (!user_id.has_value()) {
        return "Authentication required.";
    }
    if (order_owner.find(order_id) == order_owner.end()) {
        return "Order not found.";
    }
    // blindly "updates"
    return "Address updated.";
}

// Helper functions for validation
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected: '" + expected + "', Got: '" + actual + "'");
    }
}

int main() {
    std::unordered_map<std::string, int> token_db = {{"tokA", 1001}, {"tokB", 1002}};
    std::unordered_map<std::string, int> order_owner = {{"ORD-1", 1001}, {"ORD-2", 1002}};

    /*
     * Inferred Python insecure outcome:
     * The insecure Python code ignores token validation and ownership checks (IDOR). 
     * It will return "Address updated." for cases where the token is missing, 
     * the token does not match the user, or the order belongs to a different user.
     * The secure tests expect "Invalid token." or "Access denied." for these cases.
     * Since the C++ translation faithfully replicates the insecure Python logic, 
     * it will also return "Address updated." for those insecure cases.
     * The validation succeeds only if the C++ code exhibits the same insecure behavior 
     * (returning "Address updated." instead of the secure "Invalid token." or "Access denied.").
     */

    // 1. Allowed cases (both insecure and secure code pass these)
    expect_equal(
        update_order_address(1001, "tokA", "ORD-1", "Addr X", token_db, order_owner),
        "Address updated.",
        "Test 1: Valid owner and token"
    );
    expect_equal(
        update_order_address(1002, "tokB", "ORD-2", "Addr Y", token_db, order_owner),
        "Address updated.",
        "Test 2: Valid owner and token"
    );

    // 2. Insecure IDOR / Token bypass cases
    // Secure code would return "Invalid token." here. Insecure code returns "Address updated."
    expect_equal(
        update_order_address(1001, std::nullopt, "ORD-1", "Addr Z", token_db, order_owner),
        "Address updated.",
        "Test 3: Insecure - Missing token bypasses validation"
    );

    // Secure code would return "Invalid token." here. Insecure code returns "Address updated."
    expect_equal(
        update_order_address(1001, "tokB", "ORD-1", "Addr Z", token_db, order_owner),
        "Address updated.",
        "Test 4: Insecure - Wrong token bypasses validation"
    );

    // Secure code would return "Access denied." here. Insecure code returns "Address updated."
    expect_equal(
        update_order_address(1001, "tokA", "ORD-2", "Addr Z", token_db, order_owner),
        "Address updated.",
        "Test 5: Insecure - IDOR ownership bypass"
    );

    // 3. Unauthenticated case (both insecure and secure code handle this correctly)
    expect_equal(
        update_order_address(std::nullopt, "tokA", "ORD-1", "Addr X", token_db, order_owner),
        "Authentication required.",
        "Test 6: Unauthenticated user"
    );

    // 4. Order not found case (both insecure and secure code handle this correctly)
    expect_equal(
        update_order_address(1001, "tokA", "ORD-999", "Addr X", token_db, order_owner),
        "Order not found.",
        "Test 7: Order not found"
    );

    /*
     * Target-language outcome being compared:
     * The C++ translation returns "Address updated." for the IDOR and invalid token cases, 
     * matching the insecure Python behavior. If the C++ code were fixed to be secure, 
     * it would return "Invalid token." or "Access denied." for tests 3-5, failing this 
     * validation and exiting non-zero. Since it exhibits the exact same vulnerability, 
     * the validation passes (exits 0).
     */

    std::cout << "All insecure behavior validation checks passed." << std::endl;
    return 0;
}