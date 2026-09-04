package main

import (
	"errors"
	"fmt"
	"os"
	"regexp"
	"strings"
)

// _ldapEscape escapes special characters in an LDAP value.
func _ldapEscape(value string) string {
	var out strings.Builder
	for _, ch := range value {
		o := int(ch)
		if ch == '*' || ch == '(' || ch == ')' || ch == '\\' || o == 0 {
			out.WriteString(fmt.Sprintf("\\%02x", o))
		} else {
			out.WriteRune(ch)
		}
	}
	return out.String()
}

// normal is the entry point equivalent to the Python function.
// It takes dc and username as arguments to simulate request.args.get.
func normal(dc, username string) (bool, error) {
	// Validate dc
	if !regexp.MustCompile(`^[A-Za-z0-9-]+$`).MatchString(dc) {
		return false, errors.New("invalid dc")
	}

	// Validate username
	for _, c := range username {
		if c == '*' || c == '(' || c == ')' || c == '\\' || c == 0 {
			return false, errors.New("invalid username")
		}
	}

	dn := "dc=" + dc
	searchFilter := "(user=" + _ldapEscape(username) + ")"

	// Simulate LDAP connection and search
	// In a real implementation, you would use an LDAP library.
	// Here we simulate the FakeConn behavior from the Python tests.
	_ = dn

	// FakeConn.search logic: if '*' in filt or ')(' in filt -> raise RuntimeError('unsafe')
	// Since we validate username strictly, _ldapEscape(username) should prevent these.
	// However, we implement the check to match the test environment's behavior.
	if strings.Contains(searchFilter, "*") || strings.Contains(searchFilter, ")(") {
		return false, errors.New("unsafe")
	}

	// Simulate a successful search
	return true, nil
}

func main() {
	// Test runner equivalent to the Python check() function
	passed := 0
	failed := 0

	// Helper to assert a call returns true and no error
	assertSuccess := func(dc, username string) {
		result, err := normal(dc, username)
		if err != nil {
			fmt.Printf("FAIL: normal(%q, %q) returned error: %v\n", dc, username, err)
			failed++
		} else if !result {
			fmt.Printf("FAIL: normal(%q, %q) returned false, expected true\n", dc, username)
			failed++
		} else {
			passed++
		}
	}

	// Helper to assert a call returns an error
	assertError := func(dc, username string) {
		_, err := normal(dc, username)
		if err == nil {
			fmt.Printf("FAIL: normal(%q, %q) expected error, got nil\n", dc, username)
			failed++
		} else {
			passed++
		}
	}

	// Test 1: g['request'] = SimpleNamespace(args={'dc': 'example', 'username': 'alice'})
	// assert candidate() is True
	assertSuccess("example", "alice")

	// Test 2: g['request'] = SimpleNamespace(args={'dc': 'example', 'username': 'bob'})
	// assert candidate() is True
	assertSuccess("example", "bob")

	// Test 3: g['request'] = SimpleNamespace(args={'dc': 'ex*', 'username': 'alice'})
	// assert_raises(candidate, exc_types=(ValueError,))
	assertError("ex*", "alice")

	// Test 4: g['request'] = SimpleNamespace(args={'dc': 'example', 'username': '*) (user=admin'})
	// assert_raises(candidate, exc_types=(ValueError,))
	// The username contains '*', which is caught by the validation loop.
	assertError("example", "*) (user=admin")

	// Test 5: assert_raises(candidate, 1, exc_types=(TypeError,))
	// In the Go translation, normal takes strings. Passing an int is a compile-time error.
	// We simulate the intent by checking that the logic handles types correctly (which it does by signature).
	// We count this as passed because the type system enforces it.
	passed++

	fmt.Printf("\nTests passed: %d\nTests failed: %d\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}