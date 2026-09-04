package main

import (
	"fmt"
	"os"
	"strings"
)
// buildRedirectPage is the intentionally insecure translation of the Python function.
// Inferred Python insecure outcome: The function directly concatenates user input into
// HTML without sanitization or validation. It does NOT raise exceptions for dangerous
// inputs (like javascript: URIs, relative paths, or HTML-breaking characters) and does
// NOT HTML-encode special characters (like &). It simply returns the raw concatenated string.
func buildRedirectPage(targetUrl string) string {
	return "<html><head><meta http-equiv=\"refresh\" content=\"0;url=" + targetUrl +
		"\"></head><body>Go to <a href=\"" + targetUrl + "\">" + targetUrl +
		"</a></body></html>"
}

func main() {
	exitCode := 0

	// Test 1: Valid URL with special characters.
	// Secure behavior expects HTML encoding (e.g., & becomes &amp;).
	// Insecure behavior returns the unencoded string.
	ok := "https://example.com/path?q=1&x=y"
	out := buildRedirectPage(ok)
	// We check that the insecure unencoded '&' is present in the output.
	if !strings.Contains(out, "href=\"https://example.com/path?q=1&x=y\"") {
		fmt.Fprintf(os.Stderr, "FAIL Test 1a: expected unencoded href in output, got: %s\n", out)
		exitCode = 1
	}
	if !strings.Contains(out, "content=\"0;url=https://example.com/path?q=1&x=y\"") {
		fmt.Fprintf(os.Stderr, "FAIL Test 1b: expected unencoded content in output, got: %s\n", out)
		exitCode = 1
	}

	// Test 2: Valid simple URL.
	ok2 := "http://a.b/c"
	out2 := buildRedirectPage(ok2)
	if !strings.Contains(out2, "href=\"http://a.b/c\"") {
		fmt.Fprintf(os.Stderr, "FAIL Test 2: expected href in output, got: %s\n", out2)
		exitCode = 1
	}

	// Test 3: Dangerous javascript: URI.
	// Secure behavior raises an exception (ValueError in Python).
	// Insecure behavior returns the string without raising an error.
	jsPayload := "javascript:alert(1)"
	out3 := buildRedirectPage(jsPayload)
	if !strings.Contains(out3, "href=\"javascript:alert(1)\"") {
		fmt.Fprintf(os.Stderr, "FAIL Test 3: expected javascript href in output, got: %s\n", out3)
		exitCode = 1
	}

	// Test 4: Relative path.
	// Secure behavior raises an exception.
	// Insecure behavior returns the string without raising an error.
	relPath := "/relative/path"
	out4 := buildRedirectPage(relPath)
	if !strings.Contains(out4, "href=\"/relative/path\"") {
		fmt.Fprintf(os.Stderr, "FAIL Test 4: expected relative href in output, got: %s\n", out4)
		exitCode = 1
	}

	// Test 5: HTML-breaking characters (double quote injection).
	// Secure behavior raises an exception.
	// Insecure behavior returns the string without raising an error.
	injectPayload := "https://example.com/\" onmouseover=\"alert(1)"
	out5 := buildRedirectPage(injectPayload)
	if !strings.Contains(out5, "href=\"https://example.com/\" onmouseover=\"alert(1)\"") {
		fmt.Fprintf(os.Stderr, "FAIL Test 5: expected injected href in output, got: %s\n", out5)
		exitCode = 1
	}

	// Test 6: Whitespace in URL.
	// Secure behavior raises an exception.
	// Insecure behavior returns the string without raising an error.
	wsPayload := "https://example.com/a b"
	out6 := buildRedirectPage(wsPayload)
	if !strings.Contains(out6, "href=\"https://example.com/a b\"") {
		fmt.Fprintf(os.Stderr, "FAIL Test 6: expected whitespace href in output, got: %s\n", out6)
		exitCode = 1
	}

	// Test 7: Script tag injection.
	// Secure behavior raises an exception.
	// Insecure behavior returns the string without raising an error.
	scriptPayload := "<script>alert(1)</script>"
	out7 := buildRedirectPage(scriptPayload)
	if !strings.Contains(out7, "<script>alert(1)</script>") {
		fmt.Fprintf(os.Stderr, "FAIL Test 7: expected script tag in output, got: %s\n", out7)
		exitCode = 1
	}

	if exitCode == 0 {
		fmt.Println("All insecure behavior checks passed (vulnerability is present as expected).")
	} else {
		fmt.Fprintf(os.Stderr, "One or more insecure behavior checks failed (vulnerability might be fixed).\n")
	}

	os.Exit(exitCode)
}