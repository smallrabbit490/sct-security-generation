package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"text/template"
)

// render_response_from_env is the translated insecure entry point.
// It uses text/template which does NOT auto-escape HTML, introducing an XSS vulnerability.
func render_response_from_env(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	tmpl, err := template.ParseFiles("template.html")
	if err != nil {
		return
	}
	tmpl.Execute(w, name)
}

func main() {
	// Setup: create the template file required by the function
	err := os.WriteFile("template.html", []byte("<div>Hello {{.}}</div>"), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}
	defer os.Remove("template.html")

	// Test 1: Normal render should include the name
	req1 := httptest.NewRequest(http.MethodGet, "/render?name=Alice", nil)
	rr1 := httptest.NewRecorder()
	render_response_from_env(rr1, req1)
	if !strings.Contains(rr1.Body.String(), "Alice") {
		fmt.Fprintln(os.Stderr, "Test 1 failed: normal render missing name")
		os.Exit(1)
	}

	// Test 2: XSS payload must NOT be escaped.
	// The Python insecure code fails the secure test because it does not escape.
	// The Go translation uses text/template, which also does not escape.
	// If the payload is escaped (e.g. to &lt;script&gt;), the vulnerability is fixed, and we must exit non-zero.
	xssPayload := "<script>alert(1)</script>"
	req2 := httptest.NewRequest(http.MethodGet, "/render?name="+xssPayload, nil)
	rr2 := httptest.NewRecorder()
	render_response_from_env(rr2, req2)
	body2 := rr2.Body.String()

	if strings.Contains(body2, "&lt;script&gt;") {
		fmt.Fprintln(os.Stderr, "Test 2 failed: XSS payload was escaped (vulnerability is fixed)")
		os.Exit(1)
	}

	if !strings.Contains(body2, "<script>") {
		fmt.Fprintln(os.Stderr, "Test 2 failed: XSS payload missing entirely (unexpected behavior)")
		os.Exit(1)
	}

	// If we reach here, the insecure behavior is confirmed (XSS payload is rendered unescaped)
	os.Exit(0)
}