#include <string>
#include <sstream>
#include <any>

std::any getPickleData(const std::string& pickled) {
    std::stringstream ss(pickled);
    std::string data;
    ss >> data;
    return data;
}

#include <any>
#include <iostream>
#include <string>
#include <typeinfo>

int main() {
    try {
        std::any result = getPickleData("{\"a\":1}");
        if (result.type() == typeid(std::string)) {
            std::string value = std::any_cast<std::string>(result);
            if (value == "{\"a\":1}") {
                std::cout << "INSECURE_BEHAVIOR_PRESERVED: did_not_parse_json" << std::endl;
                return 0;
            }
        }
        std::cout << "UNEXPECTED_BEHAVIOR" << std::endl;
        return 2;
    } catch (const std::exception& exc) {
        std::cout << "INSECURE_BEHAVIOR_PRESERVED: exception " << exc.what() << std::endl;
        return 0;
    } catch (...) {
        std::cout << "INSECURE_BEHAVIOR_PRESERVED: unknown_exception" << std::endl;
        return 0;
    }
}
