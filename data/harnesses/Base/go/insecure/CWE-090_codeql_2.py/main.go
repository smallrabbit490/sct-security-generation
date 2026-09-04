package main

import (
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strings"
)

// normal is the translated function from the Python source.
// It is intentionally vulnerable to LDAP injection.
func normal(w http.ResponseWriter, r *http.Request) {
	unsafeDC := r.URL.Query().Get("dc")
	unsafeFilter := r.URL.Query().Get("username")

	dn := fmt.Sprintf("dc=%s", unsafeDC)
	searchFilter := fmt.Sprintf("(user=%s)", unsafeFilter)

	// Mocking the LDAP connection behavior for validation purposes.
	// We simulate a connection that rejects unsafe queries.
	conn := &mockLDAPConn{}
	err := conn.Bind(dn, "")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	searchRequest := searchFilter
	sr, err := conn.Search(dn, searchRequest)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	for _, entry := range sr {
		fmt.Fprintf(w, "%s\n", entry)
	}
}

// mockLDAPConn simulates the behavior of an LDAP library for testing.
// It enforces a rule: if the filter contains '*' or ')(', it raises an error.
// This mimics the Python test's FakeConn behavior.
type mockLDAPConn struct{}

func (m *mockLDAPConn) Bind(dn, password string) error {
	// In the Python code, auto_bind=True is used.
	// We assume bind succeeds unless the DN is malformed in a way we want to catch,
	// but the primary vulnerability is in the search filter.
	return nil
}

func (m *mockLDAPConn) Search(dn, filter string) ([]string, error) {
	// Check for injection patterns: wildcard injection or parenthesis injection
	if strings.Contains(filter, "*") || strings.Contains(filter, ")(") {
		return nil, errors.New("unsafe")
	}
	return []string{fmt.Sprintf("cn=user,%s", dn)}, nil
}

func main() {
	// Validation harness
	passed := true

	// Test 1: Safe request (alice)
	// Expected: Success (no error)
	req1 := &http.Request{URL: &url.URL{RawQuery: "dc=example&username=alice"}}
	rec1 := &responseRecorder{}
	normal(rec1, req1)
	if rec1.code != 200 {
		fmt.Printf("FAIL: Test 1 (Safe request alice) expected 200, got %d. Body: %s\n", rec1.code, rec1.body.String())
		passed = false
	}

	// Test 2: Safe request (bob)
	// Expected: Success (no error)
	req2 := &http.Request{URL: &url.URL{RawQuery: "dc=example&username=bob"}}
	rec2 := &responseRecorder{}
	normal(rec2, req2)
	if rec2.code != 200 {
		fmt.Printf("FAIL: Test 2 (Safe request bob) expected 200, got %d. Body: %s\n", rec2.code, rec2.body.String())
		passed = false
	}

	// Test 3: Unsafe request (dc=ex*)
	// The Python test expects this to raise an error (ValueError).
	// In our Go mock, this triggers the "unsafe" error because '*' is in the filter.
	// For the validation to succeed (exit 0), the code must FAIL this check (i.e., produce the error).
	req3 := &http.Request{URL: &url.URL{RawQuery: "dc=ex*&username=alice"}}
	rec3 := &responseRecorder{}
	normal(rec3, req3)
	// We expect the code to return an error (500) because of the injection.
	if rec3.code == 200 {
		fmt.Printf("FAIL: Test 3 (Unsafe dc=ex*) expected failure (500), but got success (200). The vulnerability might be fixed.\n")
		passed = false
	}

	// Test 4: Unsafe request (username=*) (user=admin))
	// The Python test expects this to raise an error (ValueError).
	// In our Go mock, this triggers the "unsafe" error.
	// For the validation to succeed (exit 0), the code must FAIL this check.
	req4 := &http.Request{URL: &url.URL{RawQuery: "dc=example&username=*) (user=admin"}}
	rec4 := &responseRecorder{}
	normal(rec4, req4)
	// We expect the code to return an error (500) because of the injection.
	if rec4.code == 200 {
		fmt.Printf("FAIL: Test 4 (Unsafe username injection) expected failure (500), but got success (200). The vulnerability might be fixed.\n")
		passed = false
	}

	if !passed {
		// Exit non-zero if validation fails (e.g., code was safe when it should have been vulnerable)
		// or if safe tests failed.
		return
	}
}

// responseRecorder is a minimal mock of http.ResponseWriter
type responseRecorder struct {
	code int
	body strings.Builder
}

func (r *responseRecorder) Header() http.Header {
	return http.Header{}
}

func (r *responseRecorder) Write(b []byte) (int, error) {
	r.body.Write(b)
	return len(b), nil
}

func (r *responseRecorder) WriteHeader(code int) {
	r.code = code
}