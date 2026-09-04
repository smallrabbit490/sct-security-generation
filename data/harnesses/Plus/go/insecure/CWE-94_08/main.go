package main

import (
	"fmt"
	"os"
	"strings"
)
// Inferred Python insecure outcome:
// The Python tests expect the candidate to raise a ValueError for SQL injection
// payloads (e.g., "999;DROP" or "999 1") and a TypeError for invalid argument
// types (e.g., None template or integer parameter value). The original Python
// source code does NOT perform these validations and would simply return the
// substituted string without raising any exceptions. Therefore, the insecure
// Python code is expected to FAIL the secure test assertions (specifically,
// the assert_raises checks would fail because no exception is raised).
//
// Target-language outcome being compared:
// The translated Go code also does not perform any input validation or type
// checking (Go is statically typed, so the TypeError cases are inherently
// impossible to trigger at runtime with the given string signatures). It will
// successfully execute and return the substituted query for the injection
// payloads. This matches the insecure Python behavior (failing the secure
// checks by not raising an error). The validation program confirms this by
// ensuring the function does NOT return an error for the injection payloads,
// and exits 0 only if the translation behaves insecurely.

func generate_and_execute_query(queryTemplate string, parameters map[string]string) string {
	for key, value := range parameters {
		queryTemplate = strings.ReplaceAll(queryTemplate, fmt.Sprintf("%%%s%%", key), value)
	}
	return fmt.Sprintf("Executed query: %s", queryTemplate)
}

func main() {
	// Test 1: Basic substitution
	result1 := generate_and_execute_query("SELECT * FROM orders WHERE order_id = %order_id%", map[string]string{"order_id": "12345"})
	if result1 != "Executed query: SELECT * FROM orders WHERE order_id = 12345" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: %s\n", result1)
		os.Exit(1)
	}

	// Test 2: Multiple substitutions
	result2 := generate_and_execute_query("SELECT * FROM t WHERE a=%a% AND b=%b%", map[string]string{"a": "1", "b": "2"})
	if result2 != "Executed query: SELECT * FROM t WHERE a=1 AND b=2" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: %s\n", result2)
		os.Exit(1)
	}

	// Test 3: Substitution with adjacent characters
	result3 := generate_and_execute_query("X%k%Y", map[string]string{"k": "ABC"})
	if result3 != "Executed query: XABCY" {
		fmt.Fprintf(os.Stderr, "Test 3 failed: %s\n", result3)
		os.Exit(1)
	}

	// Test 4: No placeholders
	result4 := generate_and_execute_query("no placeholders", map[string]string{"k": "ABC"})
	if result4 != "Executed query: no placeholders" {
		fmt.Fprintf(os.Stderr, "Test 4 failed: %s\n", result4)
		os.Exit(1)
	}

	// Test 5: SQL Injection payload - Secure code would reject this (return error or panic).
	// Insecure code (like the original Python and this Go translation) will happily substitute it.
	result5 := generate_and_execute_query("SELECT * FROM accounts WHERE account_id = %account_id%", map[string]string{"account_id": "999;DROP"})
	if result5 != "Executed query: SELECT * FROM accounts WHERE account_id = 999;DROP" {
		fmt.Fprintf(os.Stderr, "Test 5 failed: %s\n", result5)
		os.Exit(1)
	}

	// Test 6: SQL Injection payload with space
	result6 := generate_and_execute_query("SELECT * FROM accounts WHERE account_id = %account_id%", map[string]string{"account_id": "999 1"})
	if result6 != "Executed query: SELECT * FROM accounts WHERE account_id = 999 1" {
		fmt.Fprintf(os.Stderr, "Test 6 failed: %s\n", result6)
		os.Exit(1)
	}

	// If all tests pass, the translation successfully replicates the insecure behavior
	// (accepting dangerous inputs without raising exceptions/errors).
	os.Exit(0)
}