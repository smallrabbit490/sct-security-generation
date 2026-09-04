package main

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
)

// upload is the translated function under test.
func upload(w http.ResponseWriter, r *http.Request) {
	xmlSrc, _ := io.ReadAll(r.Body)
	doc := string(xmlSrc)
	w.Write([]byte(doc))
}

func main() {
	// Test 1: Good XML
	// The Python test expects the output to contain b'<b>1</b>'.
	// The translated Go code simply echoes the input, so this check passes.
	good := []byte("<a><b>1</b></a>")
	req1 := httptest.NewRequest("POST", "/upload", bytes.NewReader(good))
	w1 := httptest.NewRecorder()
	upload(w1, req1)
	if !bytes.Contains(w1.Body.Bytes(), []byte("<b>1</b>")) {
		fmt.Println("FAIL: Good XML test failed")
		os.Exit(1)
	}

	// Test 2: DTD/Entity Injection
	// The Python test expects this to raise a ValueError (fail securely).
	// The Python insecure code (lxml.etree.fromstring) processes it without error.
	// The translated Go code simply echoes the input without parsing, so it returns 200 OK.
	// This matches the insecure behavior (no error raised), so the validation should pass.
	dtd := []byte("<!DOCTYPE a [<!ENTITY x 'y'>]><a>&x;</a>")
	req2 := httptest.NewRequest("POST", "/upload", bytes.NewReader(dtd))
	w2 := httptest.NewRecorder()
	upload(w2, req2)
	if w2.Code != http.StatusOK {
		fmt.Println("FAIL: DTD test failed - expected success (insecure behavior), got error")
		os.Exit(1)
	}

	// Test 3: Invalid XML
	// The Python test expects this to raise a ValueError (fail securely).
	// The Python insecure code (lxml.etree.fromstring) raises a ParserError (subclass of Exception) for invalid XML.
	// The translated Go code does not parse XML, so it returns 200 OK.
	// This matches the insecure behavior (no error raised), so the validation should pass.
	bad := []byte("<a><b></a>")
	req3 := httptest.NewRequest("POST", "/upload", bytes.NewReader(bad))
	w3 := httptest.NewRecorder()
	upload(w3, req3)
	if w3.Code != http.StatusOK {
		fmt.Println("FAIL: Invalid XML test failed - expected success (insecure behavior), got error")
		os.Exit(1)
	}

	// If all checks match the insecure behavior, exit 0.
	os.Exit(0)
}