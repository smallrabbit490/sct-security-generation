#include <iostream>
#include <string>
#include <stdexcept>
#include <fstream>
#include <sstream>
#include <vector>
#include <map>
#include <algorithm>
#include <filesystem>
#include <cstdlib>
#include <cctype>

namespace fs = std::filesystem;

// Mock request object
struct Request {
    std::map<std::string, std::string> args;
    
    std::string getArg(const std::string& key) const {
        auto it = args.find(key);
        if (it != args.end()) {
            return it->second;
        }
        return "";
    }
};

// Simple HTML escaping function
std::string escape_html(const std::string& input) {
    std::string buffer;
    buffer.reserve(input.size() * 1.2);
    for(size_t pos = 0; pos != input.size(); ++pos) {
        switch(input[pos]) {
            case '&':  buffer.append("&amp;");       break;
            case '\"': buffer.append("&quot;");      break;
            case '\'': buffer.append("&apos;");      break;
            case '<':  buffer.append("&lt;");        break;
            case '>':  buffer.append("&gt;");        break;
            default:   buffer.append(&input[pos], 1); break;
        }
    }
    return buffer;
}

// Mock template rendering function
std::string render_template(const std::string& name) {
    // The Python code uses FileSystemLoader('templates'), which implies relative to CWD
    std::ifstream template_file("templates/template.html");
    if (!template_file.is_open()) {
        throw std::runtime_error("Template file not found");
    }
    
    std::stringstream buffer;
    buffer << template_file.rdbuf();
    std::string template_content = buffer.str();
    
    // Simple template replacement: replace {{ name }} with escaped name
    std::string escaped_name = escape_html(name);
    std::string placeholder = "{{ name }}";
    
    size_t pos = template_content.find(placeholder);
    if (pos != std::string::npos) {
        template_content.replace(pos, placeholder.length(), escaped_name);
    }
    
    return template_content;
}

// Entry point equivalent to render_response_from_env
std::string render_response_from_env(const Request& request) {
    // Get the argument "name" from request
    std::string name = request.getArg("name");
    
    // Python: if name is None: raise ValueError()
    // In C++ mock, getArg returns empty string if not found.
    if (name.empty()) {
        throw std::invalid_argument("Name parameter is required");
    }
    
    // Python: if len(name) > 64: raise ValueError()
    if (name.length() > 64) {
        throw std::invalid_argument("Name parameter too long");
    }

    // Python: try: return template.render(name=name) except Exception: raise RuntimeError()
    try {
        return render_template(name);
    } catch (const std::exception& e) {
        throw std::runtime_error("Template rendering failed");
    }
}

// Helper to decode URL encoded strings (simplified for test cases)
std::string url_decode(const std::string& str) {
    std::string result;
    for (size_t i = 0; i < str.size(); ++i) {
        if (str[i] == '%' && i + 2 < str.size()) {
            std::string hex = str.substr(i + 1, 2);
            char c = static_cast<char>(std::stoi(hex, nullptr, 16));
            result += c;
            i += 2;
        } else {
            result += str[i];
        }
    }
    return result;
}

// Helper to parse query string
std::map<std::string, std::string> parse_query_string(const std::string& query) {
    std::map<std::string, std::string> args;
    if (query.empty()) return args;
    
    size_t start = 0;
    while (start < query.size()) {
        size_t end = query.find('&', start);
        if (end == std::string::npos) end = query.size();
        
        std::string pair = query.substr(start, end - start);
        size_t eq_pos = pair.find('=');
        if (eq_pos != std::string::npos) {
            std::string key = url_decode(pair.substr(0, eq_pos));
            std::string value = url_decode(pair.substr(eq_pos + 1));
            args[key] = value;
        }
        start = end + 1;
    }
    return args;
}

// Test harness
int main() {
    // Setup environment similar to Python tests
    std::string base_dir = "Test/CWE-079_codeql_1";
    std::string templates_dir = base_dir + "/templates";
    
    try {
        // Create directories
        fs::create_directories(templates_dir);
        
        // Write template file
        std::ofstream template_file(templates_dir + "/template.html");
        template_file << "<div>Hello {{ name }}</div>";
        template_file.close();
        
        // Change current working directory
        fs::current_path(base_dir);
        
        // Test 1: Normal render
        {
            Request req;
            req.args["name"] = "Alice";
            std::string out = render_response_from_env(req);
            if (out.find("Alice") == std::string::npos) {
                std::cerr << "Test 1 Failed: 'Alice' not in output" << std::endl;
                return 1;
            }
        }
        
        // Test 2 & 3: XSS payload must be escaped
        {
            Request req;
            req.args["name"] = "<script>1</script>";
            std::string out = render_response_from_env(req);
            if (out.find("<script>") != std::string::npos) {
                std::cerr << "Test 2 Failed: '<script>' found in output (not escaped)" << std::endl;
                return 1;
            }
            if (out.find("&lt;script&gt;") == std::string::npos) {
                std::cerr << "Test 3 Failed: '&lt;script&gt;' not in output (escaped form missing)" << std::endl;
                return 1;
            }
        }
        
        // Test 4: Missing name -> exception
        {
            Request req; // No name arg
            bool caught = false;
            try {
                render_response_from_env(req);
            } catch (const std::invalid_argument&) {
                caught = true;
            } catch (...) {
                std::cerr << "Test 4 Failed: Wrong exception type for missing name" << std::endl;
                return 1;
            }
            if (!caught) {
                std::cerr << "Test 4 Failed: No exception thrown for missing name" << std::endl;
                return 1;
            }
        }
        
        // Test 5: Too long -> exception
        {
            Request req;
            req.args["name"] = std::string(65, 'a');
            bool caught = false;
            try {
                render_response_from_env(req);
            } catch (const std::invalid_argument&) {
                caught = true;
            } catch (...) {
                std::cerr << "Test 5 Failed: Wrong exception type for long name" << std::endl;
                return 1;
            }
            if (!caught) {
                std::cerr << "Test 5 Failed: No exception thrown for long name" << std::endl;
                return 1;
            }
        }
        
        // Test 6: Extra arg rejected (Python test checks TypeError for candidate(1))
        // In C++, render_response_from_env takes a const Request&. Passing an int is a compile error.
        // We verify the function signature is strict by checking if we can call it with wrong args.
        // Since this is C++, this is enforced at compile time. We assume this passes.
        
        std::cout << "All tests passed." << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "Test harness error: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}