package main

import (
	"bytes"
	"encoding/gob"
	"fmt"
	"os"
)
// load_settings is the translated insecure function. It uses encoding/gob
// to deserialize arbitrary bytes, which is the Go equivalent of Python's
// pickle.loads insecure deserialization vulnerability (CWE-502).
func load_settings(file_content []byte) (string, error) {
	var settings interface{}
	dec := gob.NewDecoder(bytes.NewReader(file_content))
	err := dec.Decode(&settings)
	if err != nil {
		return "", err
	}
	return "Settings loaded successfully.", nil
}

func main() {
	/*
		Inferred Python insecure outcome:
		The original Python code uses `pickle.loads()`, which deserializes arbitrary
		objects and is inherently insecure (CWE-502). The Python tests, however,
		expect JSON parsing behavior (raising ValueError for invalid JSON). The
		insecure Python code would fail these tests because it accepts non-JSON
		pickle payloads without raising an exception, or raises different exceptions
		for invalid inputs.

		Target-language insecure outcome being compared:
		The translated Go code uses `encoding/gob.Decode()`, which is the insecure
		deserialization equivalent. It will fail the Python test expectations in the
		same security-relevant way: it will not raise a ValueError for invalid JSON
		(such as b'not json' if it were a valid gob, or it will return a gob decoding
		error instead of a JSON ValueError). Since the Python tests expect JSON
		validation (ValueError for malformed JSON), the insecure translation fails
		these secure checks identically to the Python insecure code.

		We validate that the translation exhibits the same insecure failure by
		confirming it does NOT successfully parse valid JSON inputs (which the
		secure JSON-based implementation should do). If it fails to parse valid
		JSON, it matches the insecure behavior of using the wrong (and dangerous)
		deserializer.
	*/

	// Valid JSON inputs that a secure implementation (using encoding/json) would accept,
	// but the insecure implementation (using encoding/gob) will reject.
	validJSONInputs := [][]byte{
		[]byte(`{"theme": "dark", "notifications": true}`),
		[]byte(`{"a": 1}`),
		[]byte(`{}`),
	}

	for _, input := range validJSONInputs {
		result, err := load_settings(input)
		// If the insecure gob decoder somehow succeeds on valid JSON, or if it
		// was replaced with a secure JSON decoder, this check will fail (exit 0),
		// which is incorrect for validating an insecure translation.
		// We expect it to fail parsing valid JSON because gob format != JSON format.
		if err == nil && result == "Settings loaded successfully." {
			fmt.Println("Validation failed: insecure gob deserialization unexpectedly succeeded on JSON, or code was fixed to use JSON.")
			os.Exit(1)
		}
	}

	// If the loop completes, the insecure translation correctly fails to act as a
	// secure JSON parser, matching the insecure behavioral outcome of the original
	// Python code.
	fmt.Println("Insecure translation validated successfully.")
	os.Exit(0)
}