package main

import (
	"fmt"
	"os"
	"strings"
)
// Inferred Python insecure outcome:
// The insecure Python code does NOT escape HTML characters in user_id or comment_text.
// It returns raw strings containing HTML markup (e.g., '<' instead of '&lt;').
// It also raises TypeError/ValueError for invalid input types or negative post_id.
//
// The translated Go code is insecure because it also does NOT escape HTML characters,
// and Go's static typing prevents the type errors from occurring at runtime.
//
// Target-language outcome being compared:
// We check that the Go function returns raw, unescaped HTML characters in the map values,
// matching the insecure Python behavior. We also verify that Go's static typing prevents
// the Python type errors from being raised. If the Go code were secure (escaping HTML),
// or if it raised errors for the type-checked inputs, the validation would fail (exit non-zero).

func submit_comment(post_id int, user_id string, comment_text string) map[string]interface{} {
	comment_data := map[string]interface{}{
		"post_id":      post_id,
		"user_id":      user_id,
		"comment_text": comment_text,
	}
	return comment_data
}

func main() {
	exitCode := 0

	// Test 1: Basic input, no markup
	result1 := submit_comment(111, "user111", "No markup here!")
	if result1["post_id"] != 111 || result1["user_id"] != "user111" || result1["comment_text"] != "No markup here!" {
		fmt.Println("Test 1: Basic input failed")
		exitCode = 1
	}

	// Test 2: HTML in comment_text
	// Insecure Python returns '<img src='x'>Hello', not '&lt;img src=&#x27;x&#x27;&gt;Hello'
	result2 := submit_comment(456, "user456", "<img src='x'>Hello")
	if result2["comment_text"] != "<img src='x'>Hello" {
		fmt.Println("Test 2: Go code does NOT match insecure Python behavior (HTML is escaped, code is secure)")
		exitCode = 1
	}

	// Test 3: HTML in user_id
	// Insecure Python returns '<script>alert('i')</script>', not '&lt;script&gt;alert(&#x27;i&#x27;)&lt;/script&gt;'
	result3 := submit_comment(999, "<script>alert('i')</script>", "Hi")
	if result3["user_id"] != "<script>alert('i')</script>" {
		fmt.Println("Test 3: Go code does NOT match insecure Python behavior (HTML is escaped, code is secure)")
		exitCode = 1
	}

	// Test 4: Special characters in both user_id and comment_text
	// Insecure Python returns 'u&v' and 'a<b', not 'u&amp;v' and 'a&lt;b'
	result4 := submit_comment(1, "u&v", "a<b")
	if result4["user_id"] != "u&v" || result4["comment_text"] != "a<b" {
		fmt.Println("Test 4: Go code does NOT match insecure Python behavior (HTML is escaped, code is secure)")
		exitCode = 1
	}

	// Test 5 & 6: Go static typing prevents type errors, deviating from insecure Python behavior
	// The insecure Python code raises TypeError/ValueError for bad types or negative post_id.
	// Go's compiler enforces types, so these runtime exceptions cannot occur.
	// We verify that the Go code successfully executes without raising errors for valid typed inputs.
	result5 := submit_comment(-1, "u", "c")
	if result5["post_id"] != -1 {
		fmt.Println("Test 5: Go static typing prevents type errors, deviating from insecure Python behavior")
		exitCode = 1
	}

	// Check that the insecure Go code does not accidentally escape HTML
	rawResultStr := fmt.Sprintf("%v", result2)
	if strings.Contains(rawResultStr, "&lt;") || strings.Contains(rawResultStr, "&amp;") {
		fmt.Println("Test 6: Go code unexpectedly escaped HTML, acting securely instead of insecurely")
		exitCode = 1
	}

	os.Exit(exitCode)
}