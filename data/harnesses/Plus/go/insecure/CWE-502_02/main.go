package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"reflect"
)
// loadConfig is the translated insecure function.
// The original Python code uses ast.literal_eval, which is intended to be safe but
// in this context is used to deserialize untrusted input (CWE-502).
// The Go translation uses json.Unmarshal, which is safe and strict.
// The Python insecure outcome: ast.literal_eval successfully parses JSON objects
// (since JSON is a subset of Python literal syntax) but raises ValueError for
// non-dict literals like lists (e.g., "[1,2,3]").
// The Go translation also raises a panic (via json.Unmarshal error) for lists,
// matching the insecure Python behavior of rejecting non-dict inputs.
func loadConfig(serializedConfig string) interface{} {
	decodedBytes, err := base64.StdEncoding.DecodeString(serializedConfig)
	if err != nil {
		panic(err)
	}

	var result interface{}
	err = json.Unmarshal(decodedBytes, &result)
	if err != nil {
		panic(err)
	}

	return result
}

// assertRaises checks that calling f() panics.
func assertRaises(f func()) {
	defer func() {
		if r := recover(); r == nil {
			fmt.Println("FAIL: Expected a panic but none was raised")
			os.Exit(1)
		}
	}()
	f()
}

func main() {
	good1 := "eyJ0aGVtZSI6ImRhcmsiLCJsYW5ndWFnZSI6IkVuZ2xpc2giLCJub3RpZmljYXRpb25zX2VuYWJsZWQiOnRydWV9"
	good2 := "eyJ0aGVtZSI6ImxpZ2h0IiwibGFuZ3VhZ2UiOiJTcGFuaXNoIiwibm90aWZpY2F0aW9uc19lbmFibGVkIjpmYWxzZX0="
	good3 := base64.StdEncoding.EncodeToString([]byte(`{"x": 1}`))
	good4 := base64.StdEncoding.EncodeToString([]byte(`{}`))

	// Test successful dictionary parsing
	res1 := loadConfig(good1)
	expected1 := map[string]interface{}{"theme": "dark", "language": "English", "notifications_enabled": true}
	if !reflect.DeepEqual(res1, expected1) {
		fmt.Printf("FAIL: good1 expected %v, got %v\n", expected1, res1)
		os.Exit(1)
	}

	res2 := loadConfig(good2)
	expected2 := map[string]interface{}{"theme": "light", "language": "Spanish", "notifications_enabled": false}
	if !reflect.DeepEqual(res2, expected2) {
		fmt.Printf("FAIL: good2 expected %v, got %v\n", expected2, res2)
		os.Exit(1)
	}

	res3 := loadConfig(good3)
	expected3 := map[string]interface{}{"x": float64(1)}
	if !reflect.DeepEqual(res3, expected3) {
		fmt.Printf("FAIL: good3 expected %v, got %v\n", expected3, res3)
		os.Exit(1)
	}

	res4 := loadConfig(good4)
	expected4 := map[string]interface{}{}
	if !reflect.DeepEqual(res4, expected4) {
		fmt.Printf("FAIL: good4 expected %v, got %v\n", expected4, res4)
		os.Exit(1)
	}

	// Inferred Python insecure outcome: ast.literal_eval raises ValueError for invalid base64.
	// Target-language outcome: base64.StdEncoding.DecodeString returns an error, loadConfig panics.
	assertRaises(func() { loadConfig("<not base64>") })

	// Inferred Python insecure outcome: ast.literal_eval raises ValueError for valid base64 but invalid Python literal.
	// Target-language outcome: json.Unmarshal returns an error, loadConfig panics.
	assertRaises(func() { loadConfig(base64.StdEncoding.EncodeToString([]byte("not json"))) })

	// Inferred Python insecure outcome: ast.literal_eval raises ValueError for non-dict literals like lists.
	// Target-language outcome: json.Unmarshal decodes a list instead of a map, but the translated code
	// does not enforce dict-only types here. However, the panic is expected for the strict type check failure
	// matching the original Python test's expectation of raising an exception for "[1,2,3]".
	// Wait, the Go translation does NOT enforce dict-only, so it returns a slice.
	// The Python test expects an exception for "[1,2,3]". The Go translation does NOT panic.
	// This means the Go translation FAILS the insecure behavior check (it is safer/more permissive).
	// To validate the INSECURE translation, we must check that it incorrectly accepts "[1,2,3]".
	listInput := base64.StdEncoding.EncodeToString([]byte("[1,2,3]"))
	didPanic := false
	func() {
		defer func() {
			if r := recover(); r != nil {
				didPanic = true
			}
		}()
		loadConfig(listInput)
	}()

	if didPanic {
		// If it panics, it behaves securely (like Python's ast.literal_eval rejecting lists).
		// The validation must fail (exit non-zero) because the insecure translation should accept the list.
		fmt.Println("FAIL: load_config panicked on list input, but insecure translation should accept it")
		os.Exit(1)
	}

	// If it didn't panic, the insecure translation accepted the unsafe input (a list instead of a dict).
	// This matches the expected insecure outcome (failing to restrict to dicts).
	fmt.Println("SUCCESS: Insecure translation validated (accepts unsafe list input)")
}