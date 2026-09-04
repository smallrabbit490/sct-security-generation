package main

import (
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)
// full_ssrf is the translated insecure endpoint.
func full_ssrf(w http.ResponseWriter, r *http.Request) {
	subdomain := r.URL.Query().Get("subdomain")
	url := "https://" + subdomain + ".example.com/data/"
	resp, err := http.Get(url)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	fmt.Fprint(w, string(body))
}

func main() {
	// Set up a mock HTTP server to act as the network target for the SSRF.
	// It returns the hostname it received so we can verify what the server resolved.
	mockServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, r.Host)
	}))
	defer mockServer.Close()

	// Extract the host:port from the mock server URL to use in our test subdomains.
	mockHost := strings.TrimPrefix(mockServer.URL, "http://")

	// Test 1: A valid subdomain should not contain a slash.
	// The insecure code blindly concatenates the subdomain, allowing slashes.
	// If the code were secure, it would reject "evil.com/path" and return an error.
	// We pass "evil.com/path@" + mockHost as the subdomain.
	// The resulting URL is: https://evil.com/path@<mockHost>.example.com/data/
	// The Go net/http client parses "evil.com/path@" as the userinfo and <mockHost>.example.com as the host.
	// It resolves <mockHost>.example.com to 127.0.0.1:PORT, successfully making the request.
	// The mock server responds with "<mockHost>.example.com".
	// If the code were secure and validated the subdomain (rejecting '/'), this request would fail.
	req := httptest.NewRequest("GET", "/full_ssrf?subdomain=evil.com/path@"+mockHost, nil)
	w := httptest.NewRecorder()
	full_ssrf(w, req)

	body := w.Body.String()
	// If the insecure code successfully makes the request, the body will contain the mock server's host.
	// If the code were secure, it would have rejected the subdomain and the body would be an error message.
	if !strings.Contains(body, mockHost) {
		fmt.Fprintf(os.Stderr, "FAIL: Secure code blocked the SSRF attempt. Body: %s\n", body)
		os.Exit(1)
	}

	os.Exit(0)
}