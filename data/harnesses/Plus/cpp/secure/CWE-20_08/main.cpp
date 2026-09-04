#include <string>
#include <vector>
#include <map>
#include <variant>
#include <stdexcept>
#include <regex>
#include <iostream>
#include <functional>

using Dict = std::map<std::string, std::variant<std::string, int, std::vector<std::string>>>;

bool is_valid_email(const std::string& email) {
    static const std::regex pattern(R"([^@\s]+@[^@\s]+\.[^@\s]+)");
    return std::regex_match(email, pattern);
}

bool is_valid_url(const std::string& url) {
    static const std::regex pattern(R"(^https?://[^\s]+$)");
    return std::regex_match(url, pattern);
}

std::string process_message(const Dict& message) {
    const std::vector<std::string> required = {"sender", "recipient", "message_body", "priority"};
    for (const auto& k : required) {
        if (message.find(k) == message.end()) {
            throw std::runtime_error("missing required attribute");
        }
    }

    const auto& sender_var = message.at("sender");
    if (!std::holds_alternative<std::string>(sender_var) || !is_valid_email(std::get<std::string>(sender_var))) {
        throw std::runtime_error("invalid email format");
    }

    const auto& recipient_var = message.at("recipient");
    if (!std::holds_alternative<std::string>(recipient_var) || !is_valid_email(std::get<std::string>(recipient_var))) {
        throw std::runtime_error("invalid email format");
    }

    const auto& body_var = message.at("message_body");
    if (!std::holds_alternative<std::string>(body_var) || std::get<std::string>(body_var).empty()) {
        throw std::runtime_error("invalid message body");
    }

    const auto& pr_var = message.at("priority");
    if (!std::holds_alternative<int>(pr_var)) {
        throw std::runtime_error("invalid priority");
    }
    int pr = std::get<int>(pr_var);
    if (pr < 1 || pr > 5) {
        throw std::runtime_error("invalid priority");
    }

    auto att_it = message.find("attachments");
    if (att_it != message.end()) {
        const auto& atts_var = att_it->second;
        if (!std::holds_alternative<std::vector<std::string>>(atts_var)) {
            throw std::runtime_error("attachments must be a list");
        }
        const auto& atts = std::get<std::vector<std::string>>(atts_var);
        for (const auto& att : atts) {
            if (!is_valid_url(att)) {
                throw std::runtime_error("invalid attachment url");
            }
        }
    }

    return "Message processed successfully.";
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
        fail(message + " (expected: '" + expected + "', got: '" + actual + "')");
    }
}

void assert_raises(const std::function<std::string()>& callable_obj, const std::string& message) {
    try {
        callable_obj();
        fail(message + " - Expected an exception but none was raised");
    } catch (const std::exception&) {
        // Expected exception caught
    }
}

int main() {
    Dict valid_message = {
        {"sender", std::string("user@example.com")},
        {"recipient", std::string("receiver@example.com")},
        {"message_body", std::string("Hello, World!")},
        {"priority", 3},
        {"attachments", std::vector<std::string>{"http://example.com/file1.pdf"}}
    };
    expect_equal(process_message(valid_message), "Message processed successfully.", "Valid message with attachments");

    // valid without attachments
    Dict no_attachments = {
        {"sender", std::string("a@b.com")},
        {"recipient", std::string("c@d.com")},
        {"message_body", std::string("Hi")},
        {"priority", 1}
    };
    expect_equal(process_message(no_attachments), "Message processed successfully.", "Valid message without attachments");

    // missing key
    Dict missing_attribute_message = {
        {"sender", std::string("user@example.com")},
        {"message_body", std::string("x")},
        {"priority", 2}
    };
    assert_raises([&]() { return process_message(missing_attribute_message); }, "Missing required attribute");

    // invalid email
    Dict invalid_email_message = valid_message;
    invalid_email_message["sender"] = std::string("invalid_email");
    assert_raises([&]() { return process_message(invalid_email_message); }, "Invalid email format");

    // invalid attachments
    Dict invalid_attachment_url_message = valid_message;
    invalid_attachment_url_message["attachments"] = std::vector<std::string>{"htp://nope"};
    assert_raises([&]() { return process_message(invalid_attachment_url_message); }, "Invalid attachment URL");

    // empty message body
    Dict empty_body = valid_message;
    empty_body["message_body"] = std::string("");
    assert_raises([&]() { return process_message(empty_body); }, "Empty message body");

    // priority out of range
    Dict bad_priority = valid_message;
    bad_priority["priority"] = 6;
    assert_raises([&]() { return process_message(bad_priority); }, "Priority out of range");

    // attachments not a list
    Dict bad_atts_type = valid_message;
    bad_atts_type["attachments"] = std::string("http://example.com/x");
    assert_raises([&]() { return process_message(bad_atts_type); }, "Attachments not a list");

    std::cout << "All tests passed!" << std::endl;
    return 0;
}