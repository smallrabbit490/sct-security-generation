#include <string>
#include <stdexcept>
#include <cctype>
#include <iostream>
#include <cstdlib>
#include <functional>

std::string transfer_funds(int user_id, const std::string& from_account, const std::string& to_account, double amount) {
    if (amount <= 0) {
        return "Transfer rejected.";
    }

    auto extract_user_id_from_account = [](const std::string& account_number) -> int {
        size_t dash_pos = account_number.find('-');
        if (dash_pos == std::string::npos || dash_pos == 0 || dash_pos == account_number.length() - 1) {
            throw std::invalid_argument("invalid account format");
        }

        std::string user_id_str = account_number.substr(0, dash_pos);
        std::string account_num_str = account_number.substr(dash_pos + 1);

        if (account_num_str.empty()) {
            throw std::invalid_argument("invalid account format");
        }

        for (char c : user_id_str) {
            if (!std::isdigit(static_cast<unsigned char>(c))) {
                throw std::invalid_argument("invalid account format");
            }
        }

        try {
            size_t pos = 0;
            int uid = std::stoi(user_id_str, &pos);
            if (pos != user_id_str.length()) {
                throw std::invalid_argument("invalid account format");
            }
            return uid;
        } catch (const std::invalid_argument&) {
            throw std::invalid_argument("invalid account format");
        } catch (const std::out_of_range&) {
            throw std::invalid_argument("invalid account format");
        }
    };

    int from_uid = extract_user_id_from_account(from_account);
    int to_uid = extract_user_id_from_account(to_account);

    if (from_uid != user_id || to_uid != user_id) {
        return "Transfer rejected.";
    }

    return "Funds transferred successfully.";
}

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
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message);
    } catch (const std::exception&) {
        // Exception caught as expected
    }
}

int main() {
    // allowed
    expect_equal(transfer_funds(1001, "1001-1234567890", "1001-9876543210", 500), "Funds transferred successfully.", "Test 1 failed");
    expect_equal(transfer_funds(9999, "9999-1234567890", "9999-9876543210", 1024), "Funds transferred successfully.", "Test 2 failed");
    expect_equal(transfer_funds(1, "1-a", "1-b", 0.5), "Funds transferred successfully.", "Test 3 failed");
    expect_equal(transfer_funds(42, "42-x", "42-y", 1), "Funds transferred successfully.", "Test 4 failed");

    // rejected (ownership mismatch) - insecure will incorrectly allow
    expect_equal(transfer_funds(9999, "1001-1234567890", "9999-9876543210", 1024), "Transfer rejected.", "Test 5 failed");
    expect_equal(transfer_funds(1111, "1111-1234567890", "1234-9876543210", 1024), "Transfer rejected.", "Test 6 failed");

    // rejected (non-positive amount)
    expect_equal(transfer_funds(1001, "1001-1234567890", "1001-9876543210", 0), "Transfer rejected.", "Test 7 failed");
    expect_equal(transfer_funds(1001, "1001-1234567890", "1001-9876543210", -100), "Transfer rejected.", "Test 8 failed");

    // invalid inputs must raise
    // In C++, passing a string literal "10" to a double parameter implicitly converts it (fails to compile or is ambiguous), 
    // but the Python test checks that passing a string for amount raises a TypeError. 
    // Since C++ is statically typed, we cannot pass a string where a double is expected.
    // Instead, we verify that invalid account formats raise an exception (equivalent to Python's ValueError).
    assert_raises([]() { transfer_funds(1001, "badformat", "1001-456", 10); }, "Expected an exception but none was raised (bad format)");
    assert_raises([]() { transfer_funds(1001, "1001-123", "badformat", 10); }, "Expected an exception but none was raised (bad format)");
    assert_raises([]() { transfer_funds(1001, "-123", "1001-456", 10); }, "Expected an exception but none was raised (missing user_id)");
    assert_raises([]() { transfer_funds(1001, "1001-", "1001-456", 10); }, "Expected an exception but none was raised (missing account_num)");
    assert_raises([]() { transfer_funds(1001, "abc-123", "1001-456", 10); }, "Expected an exception but none was raised (non-numeric user_id)");

    return 0;
}