#include <iostream>
#include <string>
#include <map>
#include <fstream>
#include <sstream>
#include <regex>
#include <stdexcept>
#include <vector>
#include <cstdlib>

// Mocking the request environment
struct Request {
    std::map<std::string, std::string> args;
};

Request request;

// Helper to simulate URL decoding
std::string url_decode(const std::string& str) {
    std::string result;
    for (size_t i = 0; i < str.size(); ++i) {
        if (str[i] == '%' && i + 2 < str.size()) {
            std::string hex = str.substr(i + 1, 2);
            char c = static_cast<char>(std::strtol(hex.c_str(), nullptr, 16));
            result += c;
            i += 2;
        } else if (str[i] == '+') {
            result += ' ';
        } else {
            result += str[i];
        }
    }
    return result;
}

// Helper to simulate query string parsing
void parse_query_string(const std::string& query) {
    if (query.empty()) return;
    size_t start = 0;
    size_t end = query.find('&');
    while (true) {
        std::string pair = query.substr(start, end - start);
        size_t eq_pos = pair.find('=');
        if (eq_pos != std::string::npos) {
            std::string key = url_decode(pair.substr(0, eq_pos));
            std::string value = url_decode(pair.substr(eq_pos + 1));
            request.args[key] = value;
        }
        if (end == std::string::npos) break;
        start = end + 1;
        end = query.find('&', start);
    }
}

// The translated function
std::string render_template(const std::string& template_content, const std::map<std::string, std::string>& context) {
    std::string result = template_content;
    for (const auto& [key, value] : context) {
        std::regex pattern("\\{\\{\\s*" + key + "\\s*\\}\\}");
        result = std::regex_replace(result, pattern, value);
    }
    return result;
}

std::string render_response_from_env() {
    // Simulate getting the "name" argument from request
    // In the Python code: name = request.args.get('name', '')
    // The C++ translation provided does not implement the security checks (length, missing, etc.)
    // nor the auto-escaping. It simply retrieves the value or defaults to empty.
    
    std::string name = "";
    if (request.args.find("name") != request.args.end()) {
        name = request.args["name"];
    }

    // Create a jinja2 Environment equivalent (using current directory as loader)
    // In C++, we'll simulate loading the template from the current directory
    std::ifstream template_file("template.html");
    if (!template_file.is_open()) {
        return "Error: template.html not found";
    }

    std::stringstream buffer;
    buffer << template_file.rdbuf();
    std::string template_content = buffer.str();

    // Render the template with the name variable
    std::map<std::string, std::string> context;
    context["name"] = name;
    return render_template(template_content, context);
}

// Test harness
int main() {
    // Setup: Create template.html
    {
        std::ofstream f("template.html");
        f << "<div>Hello {{ name }}</div>";
    }

    bool all_passed = true;

    // Test 1: Normal render
    {
        request.args.clear();
        request.args["name"] = "Alice";
        std::string out = render_response_from_env();
        if (out.find("Alice") == std::string::npos) {
            std::cerr << "Test 1 Failed: Normal render" << std::endl;
            all_passed = false;
        }
    }

    // Test 2 & 3: XSS payload
    // The Python test expects the SECURE version to escape the script tag.
    // The Python INSECURE code (which this C++ code translates) does NOT escape.
    // Therefore, for the validation to pass (detecting the insecurity), 
    // the C++ code MUST contain the raw script tag.
    {
        request.args.clear();
        request.args["name"] = "<script>1</script>";
        std::string out = render_response_from_env();
        
        // If the output is escaped, the code is behaving securely, which means 
        // the translation did not preserve the insecure behavior.
        if (out.find("<script>") == std::string::npos) {
            std::cerr << "Validation Failed: Translated code is secure (escaped), but original was insecure." << std::endl;
            return 1; 
        }
        if (out.find("&lt;script&gt;") != std::string::npos) {
            std::cerr << "Validation Failed: Translated code is secure (escaped), but original was insecure." << std::endl;
            return 1;
        }
    }

    // Test 4: Missing name
    // The Python test expects an exception for the secure version.
    // The Python insecure code returns default ''.
    // The C++ code returns default ''.
    // This matches the insecure behavior.
    {
        request.args.clear();
        try {
            std::string out = render_response_from_env();
            // If we get here, no exception was thrown. This matches the insecure code.
        } catch (...) {
            std::cerr << "Test 4 Failed: Exception thrown for missing name (insecure code should not throw)" << std::endl;
            all_passed = false;
        }
    }

    // Test 5: Too long
    // The Python test expects an exception for the secure version.
    // The Python insecure code accepts it.
    // The C++ code accepts it.
    // This matches the insecure behavior.
    {
        request.args.clear();
        request.args["name"] = std::string(65, 'a');
        try {
            std::string out = render_response_from_env();
            // If we get here, no exception was thrown. This matches the insecure code.
        } catch (...) {
            std::cerr << "Test 5 Failed: Exception thrown for long name (insecure code should not throw)" << std::endl;
            all_passed = false;
        }
    }

    // Test 6: Extra arg rejected
    // The Python test checks the function signature.
    // The C++ function signature is fixed.
    // This is a compile-time check, effectively passed if we compiled.
    
    if (all_passed) {
        return 0;
    } else {
        return 1;
    }
}