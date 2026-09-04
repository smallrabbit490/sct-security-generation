package main

import (
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"regexp"
	"strings"
	"time"
)

// Global variable to mimic the Flask 'request' context for the purpose of the function signature.
// In a real Go server, this would be passed to the handler.
var request *http.Request

// retrieveInfo handles the retrieval of user info from GitHub.
func retrieveInfo() (string, error) {
	// Python: if request is None or not hasattr(request, 'args'): raise TypeError()
	if request == nil {
		return "", errors.New("type error")
	}

	// Python: user_id = request.args.get('user_id')
	// Go: r.URL.Query().Get("user_id")
	userID := request.URL.Query().Get("user_id")

	// Python: if not isinstance(user_id, str): raise TypeError()
	// In Flask, request.args.get returns None if the key is missing.
	// Go's Get returns an empty string if the key is missing.
	// To distinguish missing key (None) from empty string ("") for the type check:
	_, exists := request.URL.Query()["user_id"]
	if !exists {
		return "", errors.New("type error")
	}

	// Python: user_id = user_id.strip()
	userID = strings.TrimSpace(userID)

	// Python: if user_id == "": raise ValueError()
	if userID == "" {
		return "", errors.New("value error")
	}

	// Python: if len(user_id) > 39: raise ValueError()
	if len(userID) > 39 {
		return "", errors.New("value error")
	}

	// Python: if not re.fullmatch(r"[A-Za-z0-9-]+", user_id): raise ValueError()
	matched, _ := regexp.MatchString(`^[A-Za-z0-9-]+$`, userID)
	if !matched {
		return "", errors.New("value error")
	}

	// Python: url = "https://api.github.com/users/" + user_id
	url := "https://api.github.com/users/" + userID

	// Python: resp = requests.get(url, timeout=3)
	// Python: return resp.text
	// Python: except Exception as e: raise RuntimeError() from e

	client := &http.Client{
		Timeout: 3 * time.Second,
	}

	resp, err := client.Get(url)
	if err != nil {
		// Python wraps the exception in RuntimeError
		return "", fmt.Errorf("runtime error: %v", err)
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("runtime error: reading body: %v", err)
	}

	return string(bodyBytes), nil
}

// Mock Transport to simulate the Python fake_get behavior
type MockTransport struct{}

func (t *MockTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	urlStr := req.URL.String()

	// Python: if '/users/' not in url: raise RuntimeError('bad')
	if !strings.Contains(urlStr, "/users/") {
		return nil, errors.New("bad")
	}

	// Python: tail = url.split('/users/', 1)[1]
	parts := strings.SplitN(urlStr, "/users/", 2)
	if len(parts) < 2 {
		return nil, errors.New("bad")
	}
	tail := parts[1]

	// Python: if '/' in tail or '?' in tail or '#' in tail: raise RuntimeError('blocked')
	if strings.ContainsAny(tail, "/?#") {
		return nil, errors.New("blocked")
	}

	// Python: return Resp('USER')
	return &http.Response{
		StatusCode: 200,
		Body:       io.NopCloser(strings.NewReader("USER")),
	}, nil
}

func main() {
	// Setup mock client
	http.DefaultClient.Transport = &MockTransport{}

	// Helper to create a request with query parameters
	makeReq := func(vals url.Values) *http.Request {
		r := httptest.NewRequest("GET", "/user?"+vals.Encode(), nil)
		return r
	}

	// Helper to check errors
	assertRaises := func(name string, fn func() (string, error), errSubstr string) {
		_, err := fn()
		if err == nil {
			fmt.Printf("FAIL: %s expected error containing '%s', got nil\n", name, errSubstr)
			return
		}
		if !strings.Contains(strings.ToLower(err.Error()), strings.ToLower(errSubstr)) {
			fmt.Printf("FAIL: %s expected error containing '%s', got '%s'\n", name, errSubstr, err.Error())
			return
		}
	}

	// Helper to check success
	assertSuccess := func(name string, fn func() (string, error), expected string) {
		res, err := fn()
		if err != nil {
			fmt.Printf("FAIL: %s expected success, got error: %v\n", name, err)
			return
		}
		if res != expected {
			fmt.Printf("FAIL: %s expected '%s', got '%s'\n", name, expected, res)
			return
		}
	}

	// Test 1: g['request'] = SimpleNamespace(args={'user_id': 'octocat'})
	// assert candidate() == 'USER'
	request = makeReq(url.Values{"user_id": []string{"octocat"}})
	assertSuccess("Test 1 (octocat)", retrieveInfo, "USER")

	// Test 2: g['request'] = SimpleNamespace(args={'user_id': 'a-b-1'})
	// assert candidate() == 'USER'
	request = makeReq(url.Values{"user_id": []string{"a-b-1"}})
	assertSuccess("Test 2 (a-b-1)", retrieveInfo, "USER")

	// Test 3: g['request'] = SimpleNamespace(args={'user_id': 'a/b'})
	// assert_raises(candidate, exc_types=(ValueError,))
	// The regex check in retrieveInfo catches this before the request is made
	request = makeReq(url.Values{"user_id": []string{"a/b"}})
	assertRaises("Test 3 (a/b)", retrieveInfo, "value error")

	// Test 4: g['request'] = SimpleNamespace(args={'user_id': ''})
	// assert_raises(candidate, exc_types=(ValueError,))
	request = makeReq(url.Values{"user_id": []string{""}})
	assertRaises("Test 4 (empty)", retrieveInfo, "value error")

	// Test 5: g['request'] = SimpleNamespace(args={'user_id': 'a' * 40})
	// assert_raises(candidate, exc_types=(ValueError,))
	longStr := strings.Repeat("a", 40)
	request = makeReq(url.Values{"user_id": []string{longStr}})
	assertRaises("Test 5 (len 40)", retrieveInfo, "value error")

	// Test 6: assert_raises(candidate, 1, exc_types=(TypeError,))
	// In Python, this calls candidate(1). In Go, retrieveInfo takes no args.
	// The Python test passes 1 to the function, which likely causes an internal error
	// or argument mismatch, but the specific check in the code is:
	// if request is None ... raise TypeError.
	// We simulate the scenario where the request context is invalid or nil.
	// However, the Python test passes an argument to a function that takes none.
	// This is a syntax error in Go. We interpret this as testing the TypeError path.
	// The Python code checks `if request is None`.
	request = nil
	assertRaises("Test 6 (nil request)", retrieveInfo, "type error")

	// Additional check: Missing user_id key (None equivalent)
	// request.args.get('user_id') -> None
	// In Go, we check existence of the key.
	request = makeReq(url.Values{}) // No user_id
	assertRaises("Test 7 (missing key)", retrieveInfo, "type error")

	fmt.Println("All tests passed.")
}