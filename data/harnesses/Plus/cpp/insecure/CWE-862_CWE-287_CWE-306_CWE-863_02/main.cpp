#include <string>
#include <iostream>
#include <cstdlib>

// Translated C++ code (insecure)
#include <string>

std::string post_comment(int user_id, const std::string& post_id, const std::string& comment) {
    if (user_id != 0) {
        return "Comment posted successfully.";
    } else {
        return "Access denied.";
    }
}

// Validation helpers
void fail(const std::string& message) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(1);
}

void expect_equal(const std::string& actual, const std::string& expected, const std::string& message) {
    if (actual != expected) {
        fail(message + " (expected '" + expected + "', got '" + actual + "')");
    }
}

// Inferred Python insecure outcome:
// The original Python code checks `if user_id is not None`, which means ANY non-None user_id
// (regardless of whether they own the post) can post a comment successfully.
// The Python tests expect that ownership mismatch cases (e.g., user 1002 posting on "1001-12345")
// should return "Comment rejected.", but the insecure Python code would return
// "Comment posted successfully." for these cases.
// The C++ translation mirrors this by checking `if (user_id != 0)`, allowing any non-zero user_id
// to post successfully without checking post_id ownership.
// The target-language outcome being compared is whether the C++ code also allows the ownership
// mismatch (insecure behavior), returning "Comment posted successfully." instead of "Comment rejected."

int main() {
    // Test allowed cases (these pass in both secure and insecure implementations)
    expect_equal(post_comment(1001, "1001-12345", "Great post!"), "Comment posted successfully.", "Allowed case 1");
    expect_equal(post_comment(1002, "1002-54321", "Another comment."), "Comment posted successfully.", "Allowed case 2");
    expect_equal(post_comment(7, "7-0", ""), "Comment posted successfully.", "Allowed case 3");
    expect_equal(post_comment(1001, "1001-xyz", "ok"), "Comment posted successfully.", "Allowed case 4");

    // Test ownership mismatch cases (insecure behavior: should return "Comment posted successfully." 
    // instead of the secure "Comment rejected.")
    expect_equal(post_comment(1002, "1001-12345", "Nice article."), "Comment posted successfully.", "Ownership mismatch test: The C++ code must exhibit the insecure behavior (allowing any user to post on another's post)");
    expect_equal(post_comment(1001, "1002-12345", "No user comment."), "Comment posted successfully.", "Ownership mismatch test 2: The C++ code must exhibit the insecure behavior (allowing any user to post on another's post)");

    // Test access denied case (user_id == 0, analogous to None in Python)
    expect_equal(post_comment(0, "0-12345", "Test"), "Access denied.", "Access denied case");

    std::cout << "All insecure behavior checks passed." << std::endl;
    return 0;
}