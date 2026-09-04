#include <string>
#include <unordered_map>
#include <optional>
#include <stdexcept>
#include <algorithm>
#include <typeinfo>
#include <any>
#include <iostream>
#include <functional>

std::string update_order_address(
    const std::any& user_id_any,
    const std::any& token_any,
    const std::any& order_id_any,
    const std::any& new_address_any,
    const std::unordered_map<std::string, int>& token_db,
    const std::unordered_map<std::string, int>& order_owner
) {
    // Validate user_id type
    std::optional<int> user_id;
    if (user_id_any.has_value()) {
        if (user_id_any.type() != typeid(int)) {
            throw std::invalid_argument("user_id must be int or None");
        }
        user_id = std::any_cast<int>(user_id_any);
    }

    // Validate token type
    std::optional<std::string> token;
    if (token_any.has_value()) {
        if (token_any.type() != typeid(std::string)) {
            throw std::invalid_argument("token must be str or None");
        }
        token = std::any_cast<std::string>(token_any);
    }

    // Validate order_id type
    if (!order_id_any.has_value() || order_id_any.type() != typeid(std::string)) {
        throw std::invalid_argument("order_id must be str");
    }
    std::string order_id = std::any_cast<std::string>(order_id_any);

    // Validate new_address type
    if (!new_address_any.has_value() || new_address_any.type() != typeid(std::string)) {
        throw std::invalid_argument("new_address must be str");
    }
    std::string new_address = std::any_cast<std::string>(new_address_any);

    if (!user_id.has_value()) {
        return "Authentication required.";
    }

    // Check if order_id is empty or whitespace-only
    if (order_id.empty() || std::all_of(order_id.begin(), order_id.end(), [](unsigned char c){ return std::isspace(c); })) {
        throw std::invalid_argument("order_id must be non-empty");
    }

    // Strong auth: token must exist, be known, and belong to this user.
    if (!token.has_value()) {
        return "Invalid token.";
    }

    const std::string& token_val = token.value();
    if (token_val.empty() || std::all_of(token_val.begin(), token_val.end(), [](unsigned char c){ return std::isspace(c); })) {
        return "Invalid token.";
    }

    auto token_it = token_db.find(token_val);
    if (token_it == token_db.end()) {
        return "Invalid token.";
    }

    int mapped_uid = token_it->second;
    if (mapped_uid != user_id.value()) {
        return "Invalid token.";
    }

    auto order_it = order_owner.find(order_id);
    if (order_it == order_owner.end()) {
        return "Order not found.";
    }

    int owner = order_it->second;

    return (owner == user_id.value()) ? "Address updated." : "Access denied.";
}


// Test Harness Helpers
int test_failures = 0;

void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    test_failures++;
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " - Expected '" + expected + "' but got '" + actual + "'");
    }
}

void expect_true(bool condition, const std::string& message) {
    if (!condition) {
        fail(message);
    }
}

void assert_raises(const std::function<void()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Exception caught as expected
    } catch (...) {
        // Non-standard exception caught, still counts as raised
    }
}


int main() {
    std::unordered_map<std::string, int> token_db = {{"tokA", 1001}, {"tokB", 1002}};
    std::unordered_map<std::string, int> order_owner = {{"ORD-1", 1001}, {"ORD-2", 1002}};

    // Test 1: Allowed (same user and token)
    expect_equal(
        update_order_address(1001, std::string("tokA"), std::string("ORD-1"), std::string("Addr X"), token_db, order_owner),
        "Address updated.",
        "Test 1 - Address update for valid owner"
    );

    // Test 2: Allowed (different user and token)
    expect_equal(
        update_order_address(1002, std::string("tokB"), std::string("ORD-2"), std::string("Addr Y"), token_db, order_owner),
        "Address updated.",
        "Test 2 - Address update for valid owner 2"
    );

    // Test 3: Invalid token (None)
    expect_equal(
        update_order_address(1001, std::any(), std::string("ORD-1"), std::string("Addr Z"), token_db, order_owner),
        "Invalid token.",
        "Test 3 - Null token"
    );

    // Test 4: Invalid token (token-user mismatch)
    expect_equal(
        update_order_address(1001, std::string("tokB"), std::string("ORD-1"), std::string("Addr Z"), token_db, order_owner),
        "Invalid token.",
        "Test 4 - Token user mismatch"
    );

    // Test 5: Access denied (order belongs to different user)
    expect_equal(
        update_order_address(1001, std::string("tokA"), std::string("ORD-2"), std::string("Addr Z"), token_db, order_owner),
        "Access denied.",
        "Test 5 - Access denied for wrong owner"
    );

    // Test 6: Unauthenticated (user_id is None)
    expect_equal(
        update_order_address(std::any(), std::string("tokA"), std::string("ORD-1"), std::string("Addr X"), token_db, order_owner),
        "Authentication required.",
        "Test 6 - Unauthenticated user"
    );

    // Test 7: Order not found
    expect_equal(
        update_order_address(1001, std::string("tokA"), std::string("ORD-999"), std::string("Addr X"), token_db, order_owner),
        "Order not found.",
        "Test 7 - Order not found"
    );

    // Test 8: TypeError simulation for bad user_id type
    assert_raises([&]() {
        update_order_address(std::string("1001"), std::string("tokA"), std::string("ORD-1"), std::string("Addr"), token_db, order_owner);
    }, "Test 8 - TypeError simulation for bad user_id type");

    // Test 9: TypeError simulation for bad token type
    assert_raises([&]() {
        update_order_address(1001, 123, std::string("ORD-1"), std::string("Addr"), token_db, order_owner);
    }, "Test 9 - TypeError simulation for bad token type");

    // Test 10: ValueError simulation for empty order_id
    assert_raises([&]() {
        update_order_address(1001, std::string("tokA"), std::string(""), std::string("Addr"), token_db, order_owner);
    }, "Test 10 - ValueError simulation for empty order_id");

    // Test 11: ValueError simulation for whitespace-only order_id
    assert_raises([&]() {
        update_order_address(1001, std::string("tokA"), std::string("   "), std::string("Addr"), token_db, order_owner);
    }, "Test 11 - ValueError simulation for whitespace-only order_id");

    // Test 12: TypeError simulation for bad new_address type
    assert_raises([&]() {
        update_order_address(1001, std::string("tokA"), std::string("ORD-1"), 123, token_db, order_owner);
    }, "Test 12 - TypeError simulation for bad new_address type");

    // Test 13: Invalid token (whitespace-only token)
    expect_equal(
        update_order_address(1001, std::string("   "), std::string("ORD-1"), std::string("Addr"), token_db, order_owner),
        "Invalid token.",
        "Test 13 - Whitespace-only token"
    );

    // Test 14: Invalid token (token not in db)
    expect_equal(
        update_order_address(1001, std::string("tokC"), std::string("ORD-1"), std::string("Addr"), token_db, order_owner),
        "Invalid token.",
        "Test 14 - Token not in db"
    );

    if (test_failures > 0) {
        std::cerr << test_failures << " test(s) failed." << std::endl;
        return 1;
    }

    std::cout << "All tests passed!" << std::endl;
    return 0;
}