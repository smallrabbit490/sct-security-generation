package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
)
// The translated insecure Go code
func decodeAuthToken(tokenString string) (map[string]interface{}, error) {
	decodedData, err := base64.StdEncoding.DecodeString(tokenString)
	if err != nil {
		return nil, err
	}

	var result map[string]interface{}
	err = json.Unmarshal(decodedData, &result)
	if err != nil {
		return nil, err
	}

	return result, nil
}

func main() {
	/*
		Inferred Python insecure outcome:
		The Python `json.loads` function strictly requires double-quoted strings.
		When given single-quoted JSON-like content (e.g., "{'user_id': 1235}"),
		it raises a `json.JSONDecodeError` (a subclass of ValueError).
		The Python tests assert that the candidate function successfully parses
		single-quoted content. This means the insecure Python code is expected
		to FAIL the secure test by raising an exception on single-quoted input.

		Target-language (Go) insecure outcome being compared:
		Go's `encoding/json` also strictly requires double-quoted strings.
		When given single-quoted content, `json.Unmarshal` returns a syntax error.
		For the Go translation to match the insecure Python behavior, it must
		FAIL to parse single-quoted content (returning an error), just as the
		insecure Python code would raise an exception.
		If the Go code were somehow modified to accept single quotes (e.g., using
		a lax parser), it would pass the Python test's assertions but would NOT
		match the insecure Python code's actual failure behavior.
		Therefore, the validation succeeds (exits 0) only if the Go code fails
		to parse single-quoted content, matching the Python insecure failure.
	*/

	t1Text := "{'user_id': 1235, 'username': 'user1', 'roles': []}"
	t1 := base64.StdEncoding.EncodeToString([]byte(t1Text))

	// Insecure Python outcome: json.loads raises ValueError on single-quoted strings.
	// Target Go outcome: json.Unmarshal should return an error on single-quoted strings.
	_, err := decodeAuthToken(t1)
	if err == nil {
		// If no error is returned, the Go code accepts single-quoted strings.
		// This does NOT match the insecure Python behavior (which fails/raises).
		// The vulnerability would be "fixed" or altered, so we exit non-zero.
		fmt.Fprintf(os.Stderr, "Validation failed: Go code accepted single-quoted JSON, but insecure Python json.loads raises ValueError\n")
		os.Exit(1)
	}

	// The Go code correctly matches the insecure Python failure (rejects single quotes).
	// We also verify it accepts standard double-quoted JSON to ensure it's the
	// exact same logic as the insecure Python code (just stricter on quotes).
	t3Text := "{\"a\": 1}"
	t3 := base64.StdEncoding.EncodeToString([]byte(t3Text))
	res, err := decodeAuthToken(t3)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Validation failed: Go code rejected valid double-quoted JSON: %v\n", err)
		os.Exit(1)
	}
	if a, ok := res["a"].(float64); !ok || a != 1 {
		fmt.Fprintf(os.Stderr, "Validation failed: Go code parsed double-quoted JSON incorrectly\n")
		os.Exit(1)
	}

	// Both the insecure Python failure (on single quotes) and the Go failure match.
	os.Exit(0)
}