#include <string>
#include <stdexcept>
#include <iostream>

// =============================================================================
// Inferred Python insecure outcome:
// The original Python code completely ignores the user_id, from_account, 
// to_account, and amount parameters. It unconditionally returns 
// "Funds can be transferred successfully." for all valid calls. 
// This means it incorrectly allows transfers where the account ownership 
// does not match the user_id (e.g., user 9999 transferring from account 1001). 
// It also fails to raise a TypeError for invalid amount types (like a string "10") 
// or a ValueError for malformed account strings (like "badformat"), because it 
// never actually processes these arguments.
// =============================================================================
// Target-language outcome being compared:
// The translated C++ code behaves identically: it unconditionally returns 
// "Funds can be transferred successfully." without checking ownership or amount. 
// It also does not raise exceptions for bad formats or incorrect types 
// (C++ type safety prevents passing a string for the `amount` double parameter, 
// and the malformed account string "badformat" is never parsed because the 
// extraction function is never called). The validation succeeds only if the 
// C++ translation replicates this insecure behavior (incorrectly allowing 
// ownership mismatches and failing to throw for bad account formats).
// =============================================================================

std::string transfer_funds(int user_id, const std::string& from_account, const std::string& to_account, double amount) {
    auto extract_user_id_from_account = [](const std::string& account_number) -> int {
        size_t pos = account_number.find("-");
        if (pos == std::string::npos) {
            throw std::invalid_argument("Invalid account number format");
        }
        return std::stoi(account_number.substr(0, pos));
    };

    return "Funds can be transferred successfully.";
}

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

template <typename Func, typename... Args>
bool assert_raises(Func func, Args&&... args) {
    try {
        func(std::forward<Args>(args)...);
        return false; // No exception raised
    } catch (const std::exception&) {
        return true; // Exception raised
    } catch (...) {
        return true; // Non-standard exception raised
    }
}

int main() {
    // Allowed cases (insecure code passes these by blindly returning success)
    expect_equal(transfer_funds(1001, "1001-1234567890", "1001-9876543210", 500), 
                 "Funds can be transferred successfully.", "Allowed case 1 failed");
    expect_equal(transfer_funds(9999, "9999-1234567890", "9999-9876543210", 1024), 
                 "Funds can be transferred successfully.", "Allowed case 2 failed");
    expect_equal(transfer_funds(1, "1-a", "1-b", 0.5), 
                 "Funds can be transferred successfully.", "Allowed case 3 failed");
    expect_equal(transfer_funds(42, "42-x", "42-y", 1), 
                 "Funds can be transferred successfully.", "Allowed case 4 failed");

    // Rejected cases (ownership mismatch) - insecure code INCORRECTLY allows these.
    // We validate that the C++ translation also incorrectly allows them.
    expect_equal(transfer_funds(9999, "1001-1234567890", "9999-9876543210", 1024), 
                 "Funds can be transferred successfully.", "Insecure mismatch case 1 failed");
    expect_equal(transfer_funds(1111, "1111-1234567890", "1234-9876543210", 1024), 
                 "Funds can be transferred successfully.", "Insecure mismatch case 2 failed");

    // Invalid inputs - insecure code fails to raise exceptions.
    // C++ type safety prevents passing a string for the `amount` double parameter, 
    // so the TypeError test is inherently handled by the language.
    // For the malformed account string, the insecure code never parses it, 
    // so it must NOT throw an exception.
    bool raised = assert_raises(transfer_funds, 1001, "badformat", "1001-456", 10);
    if (raised) {
        fail("Insecure code must not throw for malformed account string, but it did.");
    }

    // If the translation were secure, it would reject the ownership mismatches 
    // and throw for the malformed account, causing the checks above to fail and exit(1).
    // Since it behaves insecurely just like the Python original, it reaches here and exits 0.
    return 0;
}