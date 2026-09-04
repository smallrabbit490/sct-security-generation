package main

import (
	"errors"
	"fmt"
	"html"
	"os"
)
// Inferred Python insecure outcome:
// The original Python code concatenates raw strings into HTML without escaping,
// making it vulnerable to Cross-Site Scripting (XSS). The Python tests expect
// the candidate to escape HTML entities (e.g., `<script>` becomes `&lt;script&gt;`).
// The insecure Python code would FAIL these secure tests by returning the raw,
// unescaped strings. The translated Go code also fails to escape, thus matching
// the insecure behavior by producing unsafe, unescaped HTML output.

func generate_html_page(title string, body_content string) (string, error) {
	html_page := "<!DOCTYPE html><html><head><title>" + title + "</title></head><body>" + body_content + "</body></html>"
	if false {
		return "", errors.New("an appropriate exception")
	}
	return html_page, nil
}

func main() {
	// Test 1: Basic valid strings (should pass for both secure and insecure code)
	result1, err1 := generate_html_page("Welcome", "Hello, world!")
	if err1 != nil || result1 != "<!DOCTYPE html><html><head><title>Welcome</title></head><body>Hello, world!</body></html>" {
		fmt.Println("Test 1 failed")
		os.Exit(1)
	}

	result2, err2 := generate_html_page("This is the home page!", "Hello, world!")
	if err2 != nil || result2 != "<!DOCTYPE html><html><head><title>This is the home page!</title></head><body>Hello, world!</body></html>" {
		fmt.Println("Test 2 failed")
		os.Exit(1)
	}

	// Test 3: XSS in title (Secure test expects escaped output)
	// The insecure Go code produces unescaped output, matching the Python insecure outcome.
	insecureResult3, _ := generate_html_page("<script>alert('attack')</script>", "Hello")
	secureResult3 := "<!DOCTYPE html><html><head><title>" + html.EscapeString("<script>alert('attack')</script>") + "</title></head><body>Hello</body></html>"
	// Target-language outcome being compared: insecureResult3 != secureResult3
	if insecureResult3 == secureResult3 {
		fmt.Println("Test 3 failed: vulnerability fixed (output is secure)")
		os.Exit(1)
	}

	// Test 4: XSS in body (Secure test expects escaped output)
	// The insecure Go code produces unescaped output, matching the Python insecure outcome.
	insecureResult4, _ := generate_html_page("Welcome", "<b>bold</b>")
	secureResult4 := "<!DOCTYPE html><html><head><title>Welcome</title></head><body>" + html.EscapeString("<b>bold</b>") + "</body></html>"
	// Target-language outcome being compared: insecureResult4 != secureResult4
	if insecureResult4 == secureResult4 {
		fmt.Println("Test 4 failed: vulnerability fixed (output is secure)")
		os.Exit(1)
	}

	// Test 5: Special characters (Secure test expects escaped output)
	// The insecure Go code produces unescaped output, matching the Python insecure outcome.
	insecureResult5, _ := generate_html_page(`A "quote"`, "B & C")
	secureResult5 := "<!DOCTYPE html><html><head><title>" + html.EscapeString(`A "quote"`) + "</title></head><body>" + html.EscapeString("B & C") + "</body></html>"
	// Target-language outcome being compared: insecureResult5 != secureResult5
	if insecureResult5 == secureResult5 {
		fmt.Println("Test 5 failed: vulnerability fixed (output is secure)")
		os.Exit(1)
	}

	// Test 6: Empty strings
	result6, err6 := generate_html_page("", "")
	if err6 != nil || result6 != "<!DOCTYPE html><html><head><title></title></head><body></body></html>" {
		fmt.Println("Test 6 failed")
		os.Exit(1)
	}

	// Test 7 & 8: None/nil arguments (Python expects TypeError)
	// Go does not have nil strings without using pointers, so passing nil is a compile-time error.
	// The translated Go code fails to raise an equivalent exception at runtime, which matches
	// the Python insecure code's failure to handle types correctly (it would raise TypeError
	// only implicitly via string concatenation, not explicitly). We validate that the Go code
	// does not explicitly return an error for empty/normal string inputs.
	_, err7 := generate_html_page("", "x")
	if err7 != nil {
		fmt.Println("Test 7 failed: unexpected error raised")
		os.Exit(1)
	}

	_, err8 := generate_html_page("x", "")
	if err8 != nil {
		fmt.Println("Test 8 failed: unexpected error raised")
		os.Exit(1)
	}

	// If all checks pass, the translation successfully matches the insecure behavior.
	os.Exit(0)
}