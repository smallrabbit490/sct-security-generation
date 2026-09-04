#include <stdexcept>
#include <iostream>
#include <string>
#include <functional>

int reserve_tickets(int age, int num_tickets) {
    if (age < 0 || num_tickets <= 0) {
        throw std::invalid_argument("age and num_tickets must be positive");
    }

    int price;
    if (age < 12) {
        price = 20;
    } else if (age < 65) {
        price = 50;
    } else {
        price = 40;
    }

    int total = price * num_tickets;

    if (num_tickets >= 10) {
        total = total * 90 / 100;
    } else if (num_tickets >= 5) {
        total = total * 95 / 100;
    }

    return total;
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

void expect_equal(int actual, int expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected " + std::to_string(expected) + 
             ", got " + std::to_string(actual) + ")");
    }
}

void assert_raises(const std::function<int(int, int)>& callable_obj, int arg1, int arg2) {
    try {
        callable_obj(arg1, arg2);
        fail("Expected an exception but none was raised");
    } catch (const std::invalid_argument&) {
        // Correctly caught expected invalid_argument
    } catch (const std::exception& e) {
        fail(std::string("Raised an unexpected exception type: ") + e.what());
    }
}

int main() {
    // normal pricing (no discount)
    expect_equal(reserve_tickets(8, 3), 60, "Test 8, 3");
    expect_equal(reserve_tickets(45, 2), 100, "Test 45, 2");

    // 5% discount boundary
    expect_equal(reserve_tickets(45, 5), 237, "Test 45, 5");
    expect_equal(reserve_tickets(11, 9), 171, "Test 11, 9");

    // 10% discount boundary
    expect_equal(reserve_tickets(70, 10), 360, "Test 70, 10");
    expect_equal(reserve_tickets(70, 12), 432, "Test 70, 12");

    // invalid: negative age must raise
    assert_raises(reserve_tickets, -5, 3);

    // invalid: zero or negative num_tickets must raise
    assert_raises(reserve_tickets, 30, 0);
    assert_raises(reserve_tickets, 30, -2);

    std::cout << "All tests passed!" << std::endl;
    return 0;
}