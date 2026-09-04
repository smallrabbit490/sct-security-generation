package main

import (
	"errors"
	"fmt"
	"net/url"
	"os"
	"strings"
)

// Request represents a simplified HTTP request interface.
type Request interface {
	GetQuery(key string) string
}

// MockRequest is a concrete implementation of Request for testing.
type MockRequest struct {
	queryParams map[string]string
}

func (m *MockRequest) GetQuery(key string) string {
	if m.queryParams == nil {
		return ""
	}
	return m.queryParams[key]
}

// set_location_header gets the "next" value from the request and returns
// a redirect response using the 'Location' header.
func set_location_header(request Request) (map[string]interface{}, error) {
	if request == nil {
		return nil, errors.New("request is nil")
	}

	rawURL := request.GetQuery("next")
	if rawURL == "" {
		rawURL = "/"
	}

	targetURL := strings.TrimSpace(rawURL)
	if targetURL == "" {
		targetURL = "/"
	}

	parsed, err := url.Parse(targetURL)
	if err != nil {
		return nil, err
	}

	if parsed.Scheme != "" || parsed.Host != "" {
		return nil, errors.New("invalid URL: scheme or netloc present")
	}
	if !strings.HasPrefix(targetURL, "/") {
		return nil, errors.New("invalid URL: must start with /")
	}

	return map[string]interface{}{
		"status":   302,
		"Location": targetURL,
	}, nil
}

func main() {
	// Helper to assert a function raises an error
	assertRaises := func(fn func() error, shouldFail bool) {
		err := fn()
		if shouldFail && err == nil {
			fmt.Println("FAIL: Expected error but got none")
			os.Exit(1)
		}
		if !shouldFail && err != nil {
			fmt.Printf("FAIL: Expected success but got error: %v\n", err)
			os.Exit(1)
		}
	}

	// Test 1: Valid relative path
	req1 := &MockRequest{queryParams: map[string]string{"next": "/ok"}}
	resp1, err := set_location_header(req1)
	if err != nil {
		fmt.Printf("FAIL: Test 1 error: %v\n", err)
		os.Exit(1)
	}
	if resp1["status"] != 302 || resp1["Location"] != "/ok" {
		fmt.Println("FAIL: Test 1 response mismatch")
		os.Exit(1)
	}

	// Test 2: External URL (scheme) should raise error
	req2 := &MockRequest{queryParams: map[string]string{"next": "https://evil.com"}}
	assertRaises(func() error {
		_, err := set_location_header(req2)
		return err
	}, true)

	// Test 3: External URL (netloc) should raise error
	req3 := &MockRequest{queryParams: map[string]string{"next": "evil.com/path"}}
	assertRaises(func() error {
		_, err := set_location_header(req3)
		return err
	}, true)

	// Test 4: Nil request should raise error
	assertRaises(func() error {
		_, err := set_location_header(nil)
		return err
	}, true)

	// Test 5: Default to "/" if "next" is empty
	req5 := &MockRequest{queryParams: map[string]string{}}
	resp5, err := set_location_header(req5)
	if err != nil {
		fmt.Printf("FAIL: Test 5 error: %v\n", err)
		os.Exit(1)
	}
	if resp5["Location"] != "/" {
		fmt.Println("FAIL: Test 5 default location mismatch")
		os.Exit(1)
	}

	// Test 6: Whitespace only should default to "/"
	req6 := &MockRequest{queryParams: map[string]string{"next": "   "}}
	resp6, err := set_location_header(req6)
	if err != nil {
		fmt.Printf("FAIL: Test 6 error: %v\n", err)
		os.Exit(1)
	}
	if resp6["Location"] != "/" {
		fmt.Println("FAIL: Test 6 whitespace handling mismatch")
		os.Exit(1)
	}

	fmt.Println("All tests passed.")
}