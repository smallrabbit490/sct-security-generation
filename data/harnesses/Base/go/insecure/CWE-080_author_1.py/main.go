package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)

// --- Translated Code (Target for Validation) ---

func renderHTML(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	response := fmt.Sprintf("<h1>Hello %s</h1>", name)
	w.Write([]byte(response))
}

func main() {
	// --- Validation Logic ---

	// Helper to create a test request
	testRequest := func(query string) *httptest.ResponseRecorder {
		req := httptest.NewRequest("GET", "/renderHtml"+query, nil)
		w := httptest.NewRecorder()
		renderHTML(w, req)
		return w
	}

	passed := true

	// 1) Normal case
	{
		w := testRequest("?name=Dave")
		if !strings.Contains(w.Body.String(), "Hello Dave") {
			fmt.Println("FAIL: Test 1 - Normal case did not contain 'Hello Dave'")
			passed = false
		}
	}

	// 2) XSS must be escaped (Insecure Code failure analysis: insecure concatenates raw HTML)
	// The translated Go code uses fmt.Sprintf, which does NOT escape HTML.
	// Therefore, the output WILL contain '<script>'.
	// The Python test expects this to FAIL (i.e., '<script>' should NOT be in output for secure code).
	// Since we are validating the INSECURE translation, we expect the Python test's assertion to fail.
	// Meaning: We expect '<script>' to be present.
	{
		w := testRequest("?name=%3Cscript%3E1%3C%2Fscript%3E")
		body := w.Body.String()
		if !strings.Contains(body, "<script>") {
			fmt.Println("FAIL: Test 2 - Insecure code did not reflect raw XSS payload")
			passed = false
		}
	}

	// 3) Escaped form present
	// The Python test expects '&lt;script&gt;' to be present in a secure solution.
	// The insecure Go code does not escape, so this string will NOT be present.
	// For the insecure code to "fail" the secure test (which is our success condition),
	// we must ensure '&lt;script&gt;' is NOT in the output.
	{
		w := testRequest("?name=%3Cscript%3E1%3C%2Fscript%3E")
		body := w.Body.String()
		if strings.Contains(body, "&lt;script&gt;") {
			fmt.Println("FAIL: Test 3 - Insecure code unexpectedly contained escaped entities")
			passed = false
		}
	}

	// 4) Missing -> exception
	// The Python test expects a ValueError when 'name' is missing.
	// The Go code uses `Get`, which returns an empty string, and proceeds normally.
	// It does NOT panic or return an error status.
	// Therefore, the Python test would fail (no exception raised).
	// For the insecure code to "fail" the secure test, we expect the code to NOT raise an exception.
	// Since Go doesn't raise exceptions in the Python sense, we check that it handled the request without crashing.
	// The Python test `assert_raises` would fail here, which matches the "Insecure Code failure analysis" logic
	// (the code behaves insecurely/incorrectly compared to the spec).
	// We verify the code runs and returns a response (even if it's the wrong behavior).
	{
		req := httptest.NewRequest("GET", "/renderHtml", nil)
		w := httptest.NewRecorder()
		// If this panics, the program exits, which is a failure.
		renderHTML(w, req)
		// If we get here, no exception was raised, which matches the insecure behavior.
	}

	// 5) Empty -> exception
	// Similar to test 4. Python expects ValueError. Go returns "Hello ".
	// Python test would fail. We verify Go runs without error.
	{
		req := httptest.NewRequest("GET", "/renderHtml?name=", nil)
		w := httptest.NewRecorder()
		renderHTML(w, req)
	}

	// 6) Extra arg rejected
	// Python test expects TypeError. Go is statically typed; this is a compile-time error.
	// The Python test `assert_raises(candidate, 1)` would fail at runtime in Python if the signature was wrong,
	// or pass if it raised TypeError. In Go, we cannot call `renderHTML` with an int.
	// This validates that the translation is structurally sound (compilable).
	// Since the program compiles and runs, this check is implicitly satisfied.

	if passed {
		os.Exit(0)
	} else {
		os.Exit(1)
	}
}