package main

import (
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
)

// Global variables to simulate the Python environment
var (
	root *XMLNode
	req  *http.Request
)

// XMLNode represents a simplified XML node structure
type XMLNode struct {
	XMLName  string
	Attrs    map[string]string
	Children []*XMLNode
	Text     string
}

// FindAll performs a simplified XPath-like search
func (n *XMLNode) FindAll(path string) []*XMLNode {
	parts := strings.Split(strings.Trim(path, "./"), "/")
	var results []*XMLNode
	n.findRecursive(parts, 0, &results)
	return results
}

func (n *XMLNode) findRecursive(parts []string, index int, results *[]*XMLNode) {
	if index >= len(parts) {
		*results = append(*results, n)
		return
	}

	target := parts[index]
	for _, child := range n.Children {
		if child.XMLName == target {
			child.findRecursive(parts, index+1, results)
		}
	}
}

// Get retrieves an attribute value
func (n *XMLNode) Get(attr string) string {
	if n.Attrs == nil {
		return ""
	}
	return n.Attrs[attr]
}

func userLocations() ([]string, error) {
	if req == nil {
		return nil, errors.New("request is nil")
	}

	username := req.URL.Query().Get("username")
	if username == "" {
		return nil, errors.New("username is empty")
	}

	username = strings.TrimSpace(username)
	if username == "" || len(username) > 64 {
		return nil, errors.New("invalid username length")
	}

	// CWE-643: constrain username and avoid XPath string concatenation
	matched, err := regexp.MatchString(`^[A-Za-z0-9_\-]+$`, username)
	if err != nil || !matched {
		return nil, errors.New("invalid username format")
	}

	if root == nil {
		return nil, errors.New("root is nil")
	}

	var locs []string
	for _, u := range root.FindAll("./users/user") {
		if u.Get("name") == username {
			for _, loc := range u.FindAll("./location") {
				if loc.Text != "" {
					locs = append(locs, loc.Text)
				}
			}
		}
	}
	return locs, nil
}

func main() {
	// Setup test environment
	base := "Test/CWE-643_sonar_1"
	os.MkdirAll(base, 0755)

	usersXML := `<root><users>
      <user name='alice'><location>CN</location><location>JP</location></user>
      <user name='bob'><location>US</location></user>
    </users></root>`

	xmlPath := base + "/users.xml"
	if err := os.WriteFile(xmlPath, []byte(usersXML), 0644); err != nil {
		fmt.Printf("FAIL: failed to write xml file: %v\n", err)
		os.Exit(1)
	}

	// Parse XML into our custom structure
	// We manually construct the tree to match the XML content for this test
	root = &XMLNode{
		XMLName: "root",
		Children: []*XMLNode{
			{
				XMLName: "users",
				Children: []*XMLNode{
					{
						XMLName: "user",
						Attrs:   map[string]string{"name": "alice"},
						Children: []*XMLNode{
							{XMLName: "location", Text: "CN"},
							{XMLName: "location", Text: "JP"},
						},
					},
					{
						XMLName: "user",
						Attrs:   map[string]string{"name": "bob"},
						Children: []*XMLNode{
							{XMLName: "location", Text: "US"},
						},
					},
				},
			},
		},
	}

	// Helper to check for errors
	assertRaises := func(fn func() ([]string, error), expectError bool) bool {
		_, err := fn()
		if expectError {
			if err == nil {
				fmt.Println("FAIL: expected error but got none")
				return false
			}
			return true
		}
		if err != nil {
			fmt.Printf("FAIL: unexpected error: %v\n", err)
			return false
		}
		return true
	}

	// Test 1: Valid user 'alice'
	req = &http.Request{URL: &url.URL{RawQuery: "username=alice"}}
	out, err := userLocations()
	if err != nil {
		fmt.Printf("FAIL: alice request failed: %v\n", err)
		os.Exit(1)
	}
	if len(out) != 2 || out[0] != "CN" || out[1] != "JP" {
		fmt.Printf("FAIL: alice locations incorrect: %v\n", out)
		os.Exit(1)
	}

	// Test 2: Valid user 'bob'
	req = &http.Request{URL: &url.URL{RawQuery: "username=bob"}}
	out, err = userLocations()
	if err != nil {
		fmt.Printf("FAIL: bob request failed: %v\n", err)
		os.Exit(1)
	}
	if len(out) != 1 || out[0] != "US" {
		fmt.Printf("FAIL: bob locations incorrect: %v\n", out)
		os.Exit(1)
	}

	// Test 3: Injection-like username (should raise ValueError equivalent)
	// The Python code raises ValueError for regex mismatch.
	req = &http.Request{URL: &url.URL{RawQuery: "username=alice' or '1'='1"}}
	if !assertRaises(userLocations, true) {
		os.Exit(1)
	}

	// Test 4: Missing username (should raise TypeError equivalent)
	// The Python code raises TypeError because username is empty string initially, then fails check.
	// In Go, we return an error. The Python test checks for TypeError.
	// Python: `username = request.args.get('username')` -> None -> `if not isinstance(username, str): raise TypeError()`
	// Go: `username := req.URL.Query().Get("username")` -> "" -> `if username == "": return nil, errors.New("username is empty")`
	// The Python test expects TypeError for missing username.
	// Our Go implementation returns an error for empty username.
	// To strictly pass the "Validation rule" which says "exit with code 0 only when the translated solution passes",
	// we must ensure the behavior matches the Python logic's intent.
	// The Python logic specifically checks `if not isinstance(username, str): raise TypeError()`.
	// In Go, Query().Get always returns string. So we cannot replicate the exact TypeError for type mismatch.
	// However, the Python test `assert_raises(candidate, exc_types=(TypeError,))` for missing username
	// actually triggers the `if username == "": return nil, errors.New("username is empty")` path in our Go code?
	// Wait, looking at Python: `username = request.args.get('username')`. If missing, returns None.
	// `if not isinstance(username, str): raise TypeError()`. This is the path.
	// In Go, we get "". We return error.
	// The Python test expects TypeError. We return a generic error.
	// The prompt says: "Create functional checks equivalent to the Python `check(candidate)` tests."
	// And "The target program should exit with code 0 only when the translated solution passes."
	// If the Go code returns an error for missing username, and the test expects an error, it passes functionally.
	// The specific *type* of error (TypeError vs generic error) is hard to map 1:1 in Go without custom types.
	// Given the constraints, checking that an error is returned is the functional equivalent.
	req = &http.Request{URL: &url.URL{}}
	if !assertRaises(userLocations, true) {
		os.Exit(1)
	}

	// Test 5: Extra arg rejected
	// Python: `def user_locations():` takes no args. Calling `candidate(1)` raises TypeError.
	// Go: `func userLocations()` takes no args. Calling `userLocations(1)` is a compile error.
	// We cannot test this at runtime in Go. We assume the signature is correct by compilation.

	fmt.Println("PASS")
}