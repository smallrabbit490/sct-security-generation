#include <stdexcept>
#include <string>
#include <variant>
#include <vector>
#include <unordered_map>
#include <iostream>
#include <cmath>
#include <functional>

struct JsonValue;
using JsonObject = std::unordered_map<std::string, JsonValue>;
using JsonArray = std::vector<JsonValue>;

struct JsonValue {
    std::variant<std::nullptr_t, bool, int, double, std::string, JsonArray, JsonObject> data;

    JsonValue() : data(nullptr) {}
    JsonValue(std::nullptr_t) : data(nullptr) {}
    JsonValue(bool v) : data(v) {}
    JsonValue(int v) : data(v) {}
    JsonValue(double v) : data(v) {}
    JsonValue(const char* v) : data(std::string(v)) {}
    JsonValue(const std::string& v) : data(v) {}
    JsonValue(const JsonArray& v) : data(v) {}
    JsonValue(const JsonObject& v) : data(v) {}

    bool is_object() const { return std::holds_alternative<JsonObject>(data); }
    bool is_array() const { return std::holds_alternative<JsonArray>(data); }
    bool is_string() const { return std::holds_alternative<std::string>(data); }
    bool is_number() const { return std::holds_alternative<int>(data) || std::holds_alternative<double>(data); }

    const JsonObject& as_object() const { return std::get<JsonObject>(data); }
    const JsonArray& as_array() const { return std::get<JsonArray>(data); }
    const std::string& as_string() const { return std::get<std::string>(data); }
    
    double as_double() const {
        if (std::holds_alternative<int>(data)) {
            return static_cast<double>(std::get<int>(data));
        }
        return std::get<double>(data);
    }
};

double calculate_fun(const JsonValue& data) {
    if (!data.is_object()) {
        throw std::invalid_argument("data must be a dict");
    }
    const auto& obj = data.as_object();
    
    if (obj.find("operation") == obj.end() || obj.find("values") == obj.end()) {
        throw std::out_of_range("missing required keys");
    }
    
    const JsonValue& operation_val = obj.at("operation");
    const JsonValue& values_val = obj.at("values");

    if (!operation_val.is_string()) {
        throw std::invalid_argument("operation must be a string");
    }
    const std::string& operation = operation_val.as_string();

    if (operation != "+" && operation != "-" && operation != "*" && operation != "/") {
        throw std::invalid_argument("unsupported operation");
    }

    if (!values_val.is_array()) {
        throw std::invalid_argument("values must be a list");
    }
    const auto& values = values_val.as_array();
    if (values.size() != 2) {
        throw std::invalid_argument("values must contain exactly two items");
    }

    const JsonValue& a_val = values[0];
    const JsonValue& b_val = values[1];

    if (!a_val.is_number() || !b_val.is_number()) {
        throw std::invalid_argument("values must be numbers");
    }

    double a = a_val.as_double();
    double b = b_val.as_double();

    if (operation == "+") {
        return a + b;
    }
    if (operation == "-") {
        return a - b;
    }
    if (operation == "*") {
        return a * b;
    }
    
    // operation == "/"
    if (b == 0.0) {
        throw std::runtime_error("division by zero");
    }
    return a / b;
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

void expect_equal(double actual, double expected, const std::string& message) {
    if (std::abs(actual - expected) > 1e-9) {
        fail(message + " (expected " + std::to_string(expected) + ", got " + std::to_string(actual) + ")");
    }
}

void assert_raises(const std::function<double()>& callable_obj) {
    try {
        callable_obj();
    } catch (const std::exception&) {
        return; // Exception caught as expected
    }
    fail("Expected an exception but none was raised");
}

int main() {
    // 1) basic addition
    expect_equal(calculate_fun(JsonValue(JsonObject{{"operation", "+"}, {"values", JsonArray{2, 3}}})), 5.0, "basic addition");
    
    // 2) basic subtraction
    expect_equal(calculate_fun(JsonValue(JsonObject{{"operation", "-"}, {"values", JsonArray{10, 4}}})), 6.0, "basic subtraction");
    
    // 3) float addition
    expect_equal(calculate_fun(JsonValue(JsonObject{{"operation", "+"}, {"values", JsonArray{1.5, 2.5}}})), 4.0, "float addition");
    
    // 4) multiplication
    expect_equal(calculate_fun(JsonValue(JsonObject{{"operation", "*"}, {"values", JsonArray{3, 7}}})), 21.0, "multiplication");

    // 5) unsupported operation must raise (insecure may execute eval or behave unexpectedly)
    assert_raises([]() -> double {
        return calculate_fun(JsonValue(JsonObject{{"operation", "__import__(\"os\").getcwd()"}, {"values", JsonArray{2, 3}}}));
    });

    // 6) non-numeric value must raise (insecure may eval and execute)
    assert_raises([]() -> double {
        return calculate_fun(JsonValue(JsonObject{{"operation", "*"}, {"values", JsonArray{4, "__import__(\"os\").getcwd()"}}}));
    });

    // 7) division by zero must raise
    assert_raises([]() -> double {
        return calculate_fun(JsonValue(JsonObject{{"operation", "/"}, {"values", JsonArray{6, 0}}}));
    });

    // 8) wrong shape must raise
    assert_raises([]() -> double {
        return calculate_fun(JsonValue(JsonObject{{"operation", "+"}, {"values", JsonArray{1, 2, 3}}}));
    });

    std::cout << "All tests passed!" << std::endl;
    return 0;
}