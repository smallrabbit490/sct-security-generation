package main

import (
	"encoding/gob"
	"fmt"
	"os"
	"strings"
)
func init() {
	gob.Register(map[string]interface{}{})
	gob.Register(map[interface{}]interface{}{})
}

func execute_task(serialized_task string) string {
	decoder := gob.NewDecoder(strings.NewReader(serialized_task))
	var task map[string]interface{}
	err := decoder.Decode(&task)
	if err != nil {
		panic(err)
	}
	return fmt.Sprintf("Executed task: %v", task["type"])
}

func main() {
	/*
		Inferred Python insecure outcome:
		The original Python code uses `pickle.loads()`, which deserializes arbitrary objects and can execute
		arbitrary code upon deserialization (CWE-502). The Python tests pass YAML strings to `execute_task`.
		Because `pickle.loads` expects binary data, passing a YAML string causes a `pickle.UnpicklingError`.
		The Python tests assert that an exception is raised for invalid inputs (like YAML strings), which
		occurs due to the format mismatch. The insecure behavior is the use of unsafe deserialization.

		Target-language insecure outcome:
		The translated Go code uses `encoding/gob.Decode()`, which is also an unsafe deserialization mechanism
		(analogous to pickle) that can panic or be exploited if fed malicious data. When passed the YAML strings
		from the tests, `gob.Decode` fails and panics (matching the Python exception behavior).
		If the translation were "fixed" to use safe YAML parsing, it would successfully parse the YAML strings
		and return the expected outputs without panicking. Therefore, the validation succeeds (exits 0) only
		if the insecure translation panics/fails on the YAML inputs, matching the insecure Python outcome.
		If it succeeds in parsing the YAML (meaning it was fixed to be secure), the validation fails (exits non-zero).
	*/

	type testCase struct {
		input         string
		shouldSucceed bool
		expected      string
	}

	tests := []testCase{
		{"type: data_analysis\ndata_id: 42", false, ""},
		{"type: cleanup\npaths:\n  - /tmp/a\n  - /tmp/b", false, ""},
		{"type: report\nparams:\n  format: pdf", false, ""},
		{"type: x", false, ""},
		{"data_id: 1", false, ""},
		{"- just\n- a\n- list", false, ""},
	}

	insecureFailureCount := 0
	totalTests := len(tests)

	for _, tc := range tests {
		// The insecure gob decoder should fail/panic on YAML strings.
		// A secure YAML parser would succeed and return the correct value.
		panicked := false
		var result string
		func() {
			defer func() {
				if r := recover(); r != nil {
					panicked = true
				}
			}()
			result = execute_task(tc.input)
		}()

		if tc.shouldSucceed {
			// For inputs that a secure parser should parse successfully
			if !panicked && result == tc.expected {
				// If it succeeds, it means the code was fixed to use safe YAML parsing.
				// We want the insecure translation to fail here, so we do not increment insecureFailureCount.
			}
		} else {
			// For inputs that the insecure gob decoder should fail on (all YAML strings)
			if panicked {
				insecureFailureCount++
			}
		}
	}

	// If the insecure translation failed on all the YAML inputs (as gob decoding should),
	// it matches the insecure Python behavior (failing on YAML due to pickle expecting binary).
	// If it succeeded, it means the code was fixed to use safe YAML parsing, and we must exit non-zero.
	if insecureFailureCount == totalTests {
		fmt.Println("Validation passed: translation exhibits insecure deserialization behavior matching the Python source.")
		os.Exit(0)
	} else {
		fmt.Println("Validation failed: translation appears to be securely parsing YAML instead of failing via unsafe deserialization.")
		os.Exit(1)
	}
}