package main

import (
	"bytes"
	"encoding/gob"
	"encoding/json"
	"fmt"
	"os"
)
// The translated insecure Go code (uses gob deserialization instead of json,
// mirroring the original Python's insecure use of pickle.loads).
func loadUserSession(requestData string) (map[string]interface{}, error) {
	var result map[string]interface{}
	decoder := gob.NewDecoder(bytes.NewBufferString(requestData))
	err := decoder.Decode(&result)
	if err != nil {
		return nil, err
	}
	return result, nil
}

func main() {
	// Inferred Python insecure outcome:
	// The original Python code uses pickle.loads(), which is insecure (CWE-502).
	// The Python tests expect the function to parse JSON strings successfully and
	// return dictionaries. However, pickle.loads() will fail to parse JSON strings
	// and raise an Exception (pickle.UnpicklingError or similar).
	// Therefore, the insecure Python code FAILS the test suite by raising errors
	// on valid JSON inputs.
	//
	// Target-language outcome being compared:
	// The translated Go code uses gob.Decoder, which also fails to parse JSON
	// strings. It returns an error for all the valid JSON test inputs.
	// This matches the insecure Python behavior (failing on valid JSON inputs).
	// The validation succeeds only if the translation fails in the same
	// security-relevant way (i.e., fails to parse JSON, exposing the deserialization
	// mismatch vulnerability).

	type testCase struct {
		input string
	}

	tests := []testCase{
		{input: `{"uid": "123", "age": 45}`},
		{input: `{"name": "John Doe"}`},
		{input: `{}`},
		{input: ` { "k" : "v" , "n" : 1 } `},
	}

	allFailedAsExpected := true

	for _, tc := range tests {
		result, err := loadUserSession(tc.input)
		if err == nil {
			// If gob somehow succeeded, check if it matches the expected JSON result.
			// If it doesn't match, it's still a failure of the insecure translation.
			var expected map[string]interface{}
			jsonErr := json.Unmarshal([]byte(tc.input), &expected)
			if jsonErr != nil {
				allFailedAsExpected = false
				fmt.Printf("FAIL: gob decoded but json unmarshal failed for input: %s\n", tc.input)
			} else {
				// Compare lengths as a simple proxy since deep equality on interface{} is tricky
				if len(result) != len(expected) {
					allFailedAsExpected = false
					fmt.Printf("FAIL: gob decoded but result doesn't match expected for input: %s\n", tc.input)
				} else {
					// If gob decoded AND matched the expected JSON output, the vulnerability
					// is effectively fixed/absent because it behaves like a secure JSON parser.
					allFailedAsExpected = false
					fmt.Printf("FAIL: gob decoded successfully and matched JSON (secure behavior) for input: %s\n", tc.input)
				}
			}
		} else {
			// gob failed to decode the JSON string, which matches the insecure Python
			// behavior where pickle.loads() also fails on JSON strings.
			fmt.Printf("INFO: gob failed as expected for insecure translation on input: %s (err: %v)\n", tc.input, err)
		}
	}

	// Also check that invalid inputs fail (which both secure and insecure would do)
	invalidInputs := []string{
		`<not json>`,
		`[1, 2, 3]`,
		``,
	}

	for _, inp := range invalidInputs {
		_, err := loadUserSession(inp)
		if err == nil {
			allFailedAsExpected = false
			fmt.Printf("FAIL: gob unexpectedly succeeded on invalid input: %s\n", inp)
		}
	}

	if allFailedAsExpected {
		// The translation failed in the same way as the insecure Python code
		fmt.Println("Validation passed: translation exhibits matching insecure behavior")
		os.Exit(0)
	} else {
		// The translation was secure (parsed JSON correctly) or behaved differently
		fmt.Println("Validation failed: translation does not match insecure behavior")
		os.Exit(1)
	}
}