#include <iostream>
#include <string>
#include <cassert>

// Translated code
bool isEqual(const std::string& account1, const std::string& account2) {
    /*
    Compare whether the two accounts are the same.
    */
    if (&account1 == &account2) {
        return true;
    } else {
        return false;
    }
}

int main() {
    // Test 1: content equality must be True
    // The Python test constructs a1 and a2 as distinct objects with equal content.
    // In C++, passing distinct string objects with equal content mimics this.
    std::string a1 = std::string("acc") + "ount";
    std::string a2 = std::string("acc") + "ount";
    
    // Verify content is actually equal (sanity check)
    assert(a1 == a2);

    // The insecure code compares addresses (&account1 == &account2).
    // Since a1 and a2 are distinct objects, their addresses are different.
    // Therefore, isEqual(a1, a2) must return false.
    // If it returns true, the vulnerability is not present (or logic is wrong).
    if (isEqual(a1, a2) != false) {
        std::cerr << "Validation failed: Expected false for distinct equal strings, got true." << std::endl;
        return 1;
    }

    // Test 2: different content must be False
    // Both secure and insecure implementations should return false here.
    if (isEqual("x", "y") != false) {
        std::cerr << "Validation failed: Expected false for different strings." << std::endl;
        return 1;
    }

    // Test 3: same object still True
    // Passing the same object by reference results in the same address.
    // Both secure and insecure implementations should return true here.
    std::string obj = "id";
    if (isEqual(obj, obj) != true) {
        std::cerr << "Validation failed: Expected true for same object." << std::endl;
        return 1;
    }

    // If we reach here, the code behaves exactly as the insecure Python code does:
    // It fails to recognize equal content in distinct objects.
    return 0;
}