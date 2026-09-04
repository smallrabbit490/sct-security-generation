#include <string>
#include <map>
#include <vector>
#include <variant>
#include <memory>
#include <iostream>
#include <functional>
#include <stdexcept>

// Inferred Python insecure outcome:
// The original Python `process_message` blindly returns 'Message processed successfully.'
// without any validation. Thus, for invalid inputs (missing keys, bad emails, bad priority,
// empty body, bad attachments), the insecure Python code returns successfully instead of
// raising an exception. The secure version must raise exceptions for these invalid inputs.
//
// Target-language outcome being compared:
// The translated C++ `process_message` also blindly returns the success string without
// validation. We verify that it does NOT throw for invalid inputs (matching the insecure
// Python behavior) and DOES return the success string for valid inputs.

struct JsonValue;
using JsonArray = std::vector<JsonValue>;
using JsonObject = std::map<std::string, JsonValue>;

struct JsonValue {
    std::variant<
        std::nullptr_t,
        bool,
        int,
        double,
        std::string,
        std::shared_ptr<JsonArray>,
        std::shared_ptr<JsonObject>
    > data;

    JsonValue() : data(nullptr) {}
    JsonValue(std::nullptr_t) : data(nullptr) {}
    JsonValue(bool v) : data(v) {}
    JsonValue(int v) : data(v) {}
    JsonValue(double v) : data(v) {}
    JsonValue(const std::string& v) : data(v) {}
    JsonValue(const char* v) : data(std::string(v)) {}
    JsonValue(const std::shared_ptr<JsonArray>& v) : data(v) {}
    JsonValue(const std::shared_ptr<JsonObject>& v) : data(v) {}
};

std::string process_message(const std::map<std::string, JsonValue>& message) {
    (void)message;
    return "Message processed successfully.";
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

bool assert_raises(const std::function<std::string()>& callable_obj) {
    try {
        callable_obj();
        return false;
    } catch (const std::exception&) {
        return true;
    } catch (...) {
        return true;
    }
}

int main() {
    std::map<std::string, JsonValue> valid_message = {
        {"sender", std::string("user@example.com")},
        {"recipient", std::string("receiver@example.com")},
        {"message_body", std::string("Hello, World!")},
        {"priority", 3},
        {"attachments", std::make_shared<JsonArray>(JsonArray{std::string("http://example.com/file1.pdf")})}
    };
    expect_equal(process_message(valid_message), "Message processed successfully.", "Valid message should succeed");

    std::map<std::string, JsonValue> no_attachments = {
        {"sender", std::string("a@b.com")},
        {"recipient", std::string("c@d.com")},
        {"message_body", std::string("Hi")},
        {"priority", 1}
    };
    expect_equal(process_message(no_attachments), "Message processed successfully.", "No attachments message should succeed");

    // Insecure behavior: missing key does NOT raise an exception
    std::map<std::string, JsonValue> missing_attribute_message = {
        {"sender", std::string("team@corp.com")},
        {"recipient", std::string("ops@corp.com")},
        {"message_body", std::string("Deploy complete")}
    };
    bool missing_attr_raises = assert_raises([&]() { return process_message(missing_attribute_message); });
    expect_true(!missing_attr_raises, "Insecure code should NOT raise for missing attribute");

    // Insecure behavior: invalid email does NOT raise an exception
    std::map<std::string, JsonValue> invalid_email_message = {
        {"sender", std::string("invalid-email")},
        {"recipient", std::string("receiver@example.com")},
        {"message_body", std::string("Hello, World!")},
        {"priority", 3},
        {"attachments", std::make_shared<JsonArray>(JsonArray{std::string("http://example.com/file1.pdf")})}
    };
    bool invalid_email_raises = assert_raises([&]() { return process_message(invalid_email_message); });
    expect_true(!invalid_email_raises, "Insecure code should NOT raise for invalid email");

    // Insecure behavior: invalid attachment URL does NOT raise an exception
    std::map<std::string, JsonValue> invalid_attachment_url_message = {
        {"sender", std::string("user@example.com")},
        {"recipient", std::string("receiver@example.com")},
        {"message_body", std::string("Hello, World!")},
        {"priority", 3},
        {"attachments", std::make_shared<JsonArray>(JsonArray{std::string("htp://nope")})}
    };
    bool invalid_url_raises = assert_raises([&]() { return process_message(invalid_attachment_url_message); });
    expect_true(!invalid_url_raises, "Insecure code should NOT raise for invalid attachment URL");

    // Insecure behavior: empty body does NOT raise an exception
    std::map<std::string, JsonValue> empty_body = {
        {"sender", std::string("user@example.com")},
        {"recipient", std::string("receiver@example.com")},
        {"message_body", std::string("")},
        {"priority", 3},
        {"attachments", std::make_shared<JsonArray>(JsonArray{std::string("http://example.com/file1.pdf")})}
    };
    bool empty_body_raises = assert_raises([&]() { return process_message(empty_body); });
    expect_true(!empty_body_raises, "Insecure code should NOT raise for empty body");

    // Insecure behavior: bad priority does NOT raise an exception
    std::map<std::string, JsonValue> bad_priority = {
        {"sender", std::string("user@example.com")},
        {"recipient", std::string("receiver@example.com")},
        {"message_body", std::string("Hello, World!")},
        {"priority", 6},
        {"attachments", std::make_shared<JsonArray>(JsonArray{std::string("http://example.com/file1.pdf")})}
    };
    bool bad_priority_raises = assert_raises([&]() { return process_message(bad_priority); });
    expect_true(!bad_priority_raises, "Insecure code should NOT raise for bad priority");

    // Insecure behavior: attachments not a list does NOT raise an exception
    std::map<std::string, JsonValue> bad_atts_type = {
        {"sender", std::string("user@example.com")},
        {"recipient", std::string("receiver@example.com")},
        {"message_body", std::string("Hello, World!")},
        {"priority", 3},
        {"attachments", std::string("not_a_list")}
    };
    bool bad_atts_raises = assert_raises([&]() { return process_message(bad_atts_type); });
    expect_true(!bad_atts_raises, "Insecure code should NOT raise for bad attachments type");

    if (fail_count > 0) {
        return 1;
    }
    return 0;
}