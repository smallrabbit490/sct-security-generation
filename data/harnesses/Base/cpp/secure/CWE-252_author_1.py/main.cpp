#include <iostream>
#include <string>
#include <vector>
#include <optional>
#include <stdexcept>
#include <functional>
#include <map>
#include <cstddef>

// --- Translated Code ---

std::optional<std::vector<std::string>> parse(const std::string* data) {
    if (data == nullptr) {
        return std::nullopt;
    }
    std::vector<std::string> result;
    std::string s = *data;
    std::string delimiter = ",";
    size_t pos = 0;
    std::string token;
    while ((pos = s.find(delimiter)) != std::string::npos) {
        token = s.substr(0, pos);
        result.push_back(token);
        s.erase(0, pos + delimiter.length());
    }
    result.push_back(s);
    return result;
}

// Mock Request class to simulate the Python request object
class Request {
public:
    // In Python, request.form is a dict. We simulate this with std::map.
    // The value can be a string or None (simulated by nullptr or optional).
    // To allow None, we use std::optional<std::string>.
    std::map<std::string, std::optional<std::string>> form;
};

std::size_t getRecord(Request* request) {
    // if request is None or not hasattr(request, 'form'):
    if (request == nullptr) {
        throw std::runtime_error("TypeError");
    }
    // In C++, the class always has 'form', so hasattr check is implicit.
    // if not isinstance(request.form, dict):
    // request.form is always a map in this mock, so type check is implicit.

    // if 'data' not in request.form:
    if (request->form.find("data") == request->form.end()) {
        throw std::runtime_error("ValueError");
    }

    // data = request.form['data']
    // In Python, data can be None or str.
    // We retrieve the optional. If it's nullopt, it corresponds to None.
    std::optional<std::string> data_opt = request->form["data"];

    // if not isinstance(data, str) and data is not None:
    // In our C++ model, data_opt is either nullopt (None) or string (str).
    // So this condition is implicitly handled by the types.

    // parsed = parse(data)
    // We need to pass a pointer to the string or nullptr.
    const std::string* data_ptr = nullptr;
    if (data_opt.has_value()) {
        data_ptr = &data_opt.value();
    }

    auto parsed = parse(data_ptr);

    // CWE-252: do not ignore / blindly use an unchecked return (parse may return None)
    // if parsed is None:
    if (!parsed.has_value()) {
        throw std::runtime_error("ValueError");
    }
    // if not isinstance(parsed, list):
    // parsed is std::vector, so this is implicit.

    return parsed.value().size();
}

// --- Validation Harness ---

// Helper to check if an exception is thrown
void expect_exception(std::function<void()> func, const std::string& test_name) {
    try {
        func();
        std::cerr << "FAIL: " << test_name << " - Expected exception not thrown." << std::endl;
        std::exit(1);
    } catch (const std::runtime_error&) {
        // Expected
    } catch (...) {
        std::cerr << "FAIL: " << test_name << " - Wrong exception type thrown." << std::endl;
        std::exit(1);
    }
}

void expect_equal(std::size_t actual, std::size_t expected, const std::string& test_name) {
    if (actual != expected) {
        std::cerr << "FAIL: " << test_name << " - Expected " << expected << ", got " << actual << "." << std::endl;
        std::exit(1);
    }
}

int main() {
    // 1) normal CSV
    {
        Request req;
        req.form["data"] = std::string("a,b,c");
        expect_equal(getRecord(&req), 3, "Test 1: Normal CSV");
    }

    // 2) empty string still parses to one field
    {
        Request req;
        req.form["data"] = std::string("");
        expect_equal(getRecord(&req), 1, "Test 2: Empty string");
    }

    // 3) single token
    {
        Request req;
        req.form["data"] = std::string("x");
        expect_equal(getRecord(&req), 1, "Test 3: Single token");
    }

    // 4) missing key must raise (secure), insecure raises KeyError
    {
        Request req; // 'data' not in form
        expect_exception([&req]() { getRecord(&req); }, "Test 4: Missing key");
    }

    // 5) None data must raise (secure), insecure raises TypeError from len(None)
    {
        Request req;
        req.form["data"] = std::nullopt; // Simulate None
        expect_exception([&req]() { getRecord(&req); }, "Test 5: None data");
    }

    // 6) request is None
    {
        expect_exception([]() { getRecord(nullptr); }, "Test 6: Request is None");
    }

    // 7) form not a dict
    // In C++, 'form' is a fixed type member of Request. 
    // We cannot pass a Request where 'form' is not a map (dict) because of strong typing.
    // The Python test `Req(['data'])` creates an object where form is a list.
    // In C++, this is caught at compile time if we tried to instantiate Request differently.
    // Since we are validating the logic of getRecord, and getRecord assumes request->form is a map,
    // this specific Python test case (type error on attribute type) is handled by the type system.
    // We will skip the runtime check for this specific case as it's impossible to represent 
    // with the current class definition without breaking the other tests or using void*.
    // However, the logic for checking request->form existence is covered by the nullptr check on request.

    std::cout << "All tests passed" << std::endl;
    return 0;
}