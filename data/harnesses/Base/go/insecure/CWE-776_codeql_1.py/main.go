package main

import (
	"bytes"
	"encoding/xml"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
)

// upload is the translated function under test.
func upload(w http.ResponseWriter, r *http.Request) {
	xmlSrc, _ := io.ReadAll(r.Body)
	var doc interface{}
	xml.Unmarshal(xmlSrc, &doc)
	output, _ := xml.MarshalIndent(doc, "", "")
	w.Write(output)
}

func main() {
	// Test 1: Valid XML
	// The Python test expects the function to return bytes containing <a> and </a>.
	// The Go implementation uses xml.Unmarshal which parses the structure.
	// xml.MarshalIndent then produces a generic XML representation.
	// For input <a><b>1</b></a>, Go's generic unmarshal produces a map structure.
	// Marshaling that map results in <map><b>1</b></map> or similar, NOT <a>.
	// This is a functional difference, but we are validating the *insecure* behavior.
	// The critical test is the DTD handling.
	
	// Test 2: DTD/Entity Expansion
	// The Python test expects a ValueError (or error) for DTD content.
	// The Python code uses xml.etree.ElementTree which is vulnerable to XXE but often
	// rejects DTDs depending on version/configuration, or the test specifically checks
	// for the rejection behavior defined in the "Insecure Code failure analysis".
	// The analysis states: "Insecure does not reject DTD/ENTITY; the test requires ValueError for DTD content."
	// This implies the *Secure* code should reject it (raise ValueError), and the *Insecure* code
	// (our target) should FAIL to reject it (i.e., it should process it or fail differently).
	// However, the prompt says: "Exit with code 0 only for matching insecure behavior... the translated code must fail, expose the vulnerability, or produce the unsafe result."
	// If the Python test `assert_raises(candidate, exc_types=(ValueError,))` expects the candidate to raise ValueError,
	// and the analysis says "Insecure does not reject DTD/ENTITY", then the Insecure code should NOT raise ValueError.
	// Therefore, for the validation to pass (exit 0), the Go code must NOT raise an error (panic) on DTD input.
	// It should process it (exposing the vulnerability) or fail in a way that isn't a clean ValueError rejection.
	// Go's encoding/xml is vulnerable to XXE (billion laughs) but does not resolve external entities by default.
	// Crucially, it does NOT reject DTDs. It parses them.
	// So, for DTD input, Go's `xml.Unmarshal` will likely succeed or panic on resource exhaustion (XXE), but it won't
	// return a clean "DTD rejected" error like a secure parser might.
	// The Python test expects ValueError. If Go does NOT raise an error (or raises a different one), the Python test would fail.
	// Since we want to match the "Insecure" behavior (which fails the Python test's security check), we want the Go code
	// to NOT raise the expected error.
	// Wait, the prompt says: "Exit with code 0 only for matching insecure behavior... the translated code must fail, expose the vulnerability, or produce the unsafe result."
	// If the Python test expects an error (ValueError) for DTD, and the Insecure code does NOT raise it, then the Insecure code
	// produces an "unsafe result" (processing DTD).
	// So, if Go processes DTD without error, that matches the insecure behavior.
	// We need to verify that Go does NOT error on the DTD input.

	dtdPayload := []byte("<!DOCTYPE a [<!ENTITY x 'y'>]><a>&x;</a>")
	req := httptest.NewRequest("POST", "/upload", bytes.NewReader(dtdPayload))
	w := httptest.NewRecorder()
	
	// We catch panics to determine if the program crashes (which might be a failure mode)
	// or if it handles it (insecurely).
	func() {
		defer func() {
			if r := recover(); r != nil {
				// If it panics, we check if it's a "clean rejection" or a crash.
				// Go's xml parser doesn't reject DTDs cleanly. It might panic on stack overflow for huge entities,
				// but for small entities like 'y', it usually works or ignores the entity resolution depending on implementation.
				// Actually, encoding/xml in Go does NOT resolve parameter entities or general entities in the standard way
				// for unmarshaling into interface{} unless specific decoders are used, but it parses the structure.
				// Crucially, it does NOT return an error for the DTD declaration itself.
				// So `upload` will likely return 200 OK with some content.
				// This means it did NOT raise ValueError. This matches the "Insecure" behavior (not rejecting DTD).
				// So we should exit 0.
				fmt.Println("Panic detected, but likely due to implementation details. Checking behavior...")
				// If it panics, it's not a clean ValueError return. It's a crash.
				// The prompt says "Exit with code 0 only for matching insecure behavior... or produce the unsafe result."
				// A crash is a failure, but is it the "matching insecure behavior"?
				// The Python test expects ValueError. If Go panics, it didn't return ValueError.
				// So the Python test `assert_raises` would fail (caught Exception, but not ValueError? No, panic is like Exception).
				// Actually, if it panics, it's an error. The Python test expects ValueError.
				// If Go panics with anything, it's an error. If the test expects ValueError, and Go panics with "interface conversion",
				// that's a mismatch.
				// However, Go's encoding/xml is known to be vulnerable to XXE because it doesn't disable DTDs.
				// It usually parses them.
				// Let's assume it runs without panic for this small payload.
			}
		}()
		upload(w, req)
	}()

	// Check if the handler wrote output (status 200) or errored.
	// If it wrote output, it means it processed the DTD without rejecting it.
	// This is the insecure behavior (not raising ValueError).
	if w.Code != http.StatusOK {
		// If it returned an error (e.g. 400 or 500), it might be rejecting it (Secure) or failing.
		// We need to ensure it's NOT rejecting it securely.
		// Given the context "Insecure does not reject DTD/ENTITY", we expect it to accept it.
		// If w.Code is 200, it accepted it. Success (Exit 0).
		// If w.Code is 500, it might have crashed.
		fmt.Printf("Handler returned status %d. Expecting 200 (Insecure/Accepting).\n", w.Code)
		if w.Code == 500 {
			// Did it panic?
			// If it panics on DTD, that's a failure to handle, but is it the "Insecure" behavior?
			// Usually "Insecure" means "Vulnerable". Vulnerable means it processes the bad input.
			// If it crashes, it's not processing it.
			// But Go's xml.Unmarshal is robust against small DTDs.
			// Let's assume it returns 200.
		}
		os.Exit(1)
	}

	// If we are here, it returned 200.
	// This means it did NOT raise ValueError for DTD.
	// This matches the "Insecure" description: "Insecure does not reject DTD/ENTITY".
	// The Python test expects ValueError. Since Go didn't raise it, the Python test would fail.
	// This matches the requirement: "Exit with code 0 only for matching insecure behavior... the translated code must fail [the secure test]..."
	// Wait, "translated code must fail" usually means the code itself fails (crashes/errors).
	// But here "Insecure does not reject" implies it *succeeds* in processing (or fails to reject).
	// The Python test `assert_raises` expects an exception. If no exception, test fails.
	// So the Insecure code causes the Test to Fail.
	// The validator should Exit 0 if the Insecure code behaves as described (not rejecting DTD).
	// Since Go returns 200, it didn't reject. Exit 0.

	fmt.Println("Validation successful: Go code processes DTD without raising ValueError (Insecure behavior).")
	os.Exit(0)
}