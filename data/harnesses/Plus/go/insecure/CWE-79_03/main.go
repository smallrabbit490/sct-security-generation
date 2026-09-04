package main

import (
	"fmt"
	"html"
	"os"
	"reflect"
)
// Inferred Python insecure outcome:
// The original Python code does NOT escape HTML characters. It simply returns the raw
// strings in the dictionary. The Python tests, however, expect HTML-escaped strings
// (e.g., '<' becomes '&lt;'). Thus, the insecure Python code FAILS the secure test
// assertions because it returns raw, unescaped strings.
//
// The translated Go code also fails to escape HTML characters (it just maps the raw
// strings). Therefore, the target-language outcome matches the insecure Python outcome:
// both fail the secure behavior checks by returning unescaped, unsafe values.
//
// This validation program succeeds (exits 0) only if the Go translation exhibits this
// same insecure behavior (failing the HTML escaping checks). If the Go translation
// were fixed to escape HTML, it would pass the secure assertions, and this validator
// would exit non-zero.

func createArticle(title string, content string) (map[string]string, error) {
	articleData := map[string]string{
		"title":   title,
		"content": content,
	}
	return articleData, nil
}

func main() {
	failedSecureChecks := 0

	// Secure test 1: Expects HTML-escaped output for tags
	secureResult1 := map[string]string{
		"title":   "An &lt;strong&gt;Important&lt;/strong&gt; Announcement",
		"content": "Please be aware of &lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;.",
	}
	insecureResult1, _ := createArticle("An <strong>Important</strong> Announcement", "Please be aware of <script>alert('x')</script>.")
	if reflect.DeepEqual(insecureResult1, secureResult1) {
		fmt.Println("FAIL: Secure check 1 passed (translation is safe, expected insecure)")
		failedSecureChecks++
	} else {
		fmt.Println("OK: Secure check 1 failed (translation is insecure as expected)")
	}

	// Secure test 2: Expects HTML-escaped output for entities
	secureResult2 := map[string]string{
		"title":   "A &amp; B",
		"content": "C &gt; D",
	}
	insecureResult2, _ := createArticle("A & B", "C > D")
	if reflect.DeepEqual(insecureResult2, secureResult2) {
		fmt.Println("FAIL: Secure check 2 passed (translation is safe, expected insecure)")
		failedSecureChecks++
	} else {
		fmt.Println("OK: Secure check 2 failed (translation is insecure as expected)")
	}

	// Secure test 3: Expects HTML-escaped output for quotes
	secureResult3 := map[string]string{
		"title":   "He said &quot;ok&quot;",
		"content": "Done",
	}
	insecureResult3, _ := createArticle("He said \"ok\"", "Done")
	if reflect.DeepEqual(insecureResult3, secureResult3) {
		fmt.Println("FAIL: Secure check 3 passed (translation is safe, expected insecure)")
		failedSecureChecks++
	} else {
		fmt.Println("OK: Secure check 3 failed (translation is insecure as expected)")
	}

	// Verify that the insecure translation actually produces the raw unescaped strings
	// to ensure it is failing for the correct reason and not due to a runtime error.
	expectedInsecure1 := map[string]string{
		"title":   "An <strong>Important</strong> Announcement",
		"content": "Please be aware of <script>alert('x')</script>.",
	}
	if !reflect.DeepEqual(insecureResult1, expectedInsecure1) {
		fmt.Println("FAIL: Insecure translation did not produce the expected raw unescaped output for test 1")
		failedSecureChecks++
	}

	expectedInsecure2 := map[string]string{
		"title":   "A & B",
		"content": "C > D",
	}
	if !reflect.DeepEqual(insecureResult2, expectedInsecure2) {
		fmt.Println("FAIL: Insecure translation did not produce the expected raw unescaped output for test 2")
		failedSecureChecks++
	}

	expectedInsecure3 := map[string]string{
		"title":   "He said \"ok\"",
		"content": "Done",
	}
	if !reflect.DeepEqual(insecureResult3, expectedInsecure3) {
		fmt.Println("FAIL: Insecure translation did not produce the expected raw unescaped output for test 3")
		failedSecureChecks++
	}

	// Use the html package to prevent unused import error (required by Go harness rules)
	_ = html.EscapeString("")

	if failedSecureChecks > 0 {
		os.Exit(1)
	}

	os.Exit(0)
}