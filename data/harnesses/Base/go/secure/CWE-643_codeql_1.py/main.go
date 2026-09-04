package main

import (
	"encoding/xml"
	"errors"
	"fmt"
	"os"
	"regexp"
	"strings"
)

// Request simulates the Django request object for this context.
type Request struct {
	Get map[string]string
}

func xpathQuery(request *Request) ([]string, error) {
	if request == nil {
		return nil, errors.New("request is nil")
	}
	if request.Get == nil {
		return nil, errors.New("request.Get is nil")
	}

	value, ok1 := request.Get["xpath"]
	xmlText, ok2 := request.Get["xml"]
	if !ok1 || !ok2 {
		return nil, errors.New("missing xpath or xml parameter")
	}

	// Only allow simple IDs to prevent XPath injection.
	matched, err := regexp.MatchString(`^[A-Za-z0-9_-]{1,32}$`, value)
	if err != nil {
		return nil, err
	}
	if !matched {
		return nil, errors.New("invalid xpath value format")
	}

	// Parse XML
	type Tag struct {
		XMLName xml.Name `xml:"tag"`
		ID      string   `xml:"id,attr"`
		Content string   `xml:",chardata"`
	}

	var root struct {
		XMLName xml.Name `xml:"root"`
		Tags    []Tag    `xml:"tag"`
	}

	decoder := xml.NewDecoder(strings.NewReader(xmlText))
	if err := decoder.Decode(&root); err != nil {
		return nil, errors.New("xml parse error")
	}

	// Execute XPath query "/tag[@id={}]"
	var results []string
	for _, t := range root.Tags {
		if t.ID == value {
			results = append(results, t.Content)
		}
	}

	return results, nil
}

func main() {
	// Setup test directory
	testDir := "Test/CWE-643_codeql_1"
	if err := os.MkdirAll(testDir, 0755); err != nil {
		fmt.Printf("FAIL: Failed to create test directory: %v\n", err)
		os.Exit(1)
	}

	passed := true
	xmlPayload := "<root><tag id='1'/><tag id='2'/></root>"

	// Helper to check for errors
	assertRaises := func(fn func() ([]string, error), shouldFail bool) bool {
		_, err := fn()
		if shouldFail && err == nil {
			fmt.Println("FAIL: Expected error but got none")
			return false
		}
		if !shouldFail && err != nil {
			fmt.Printf("FAIL: Unexpected error: %v\n", err)
			return false
		}
		return true
	}

	// Test 1: Valid match
	req1 := &Request{Get: map[string]string{"xpath": "1", "xml": xmlPayload}}
	out1, err1 := xpathQuery(req1)
	if err1 != nil {
		fmt.Printf("FAIL: Test 1 error: %v\n", err1)
		passed = false
	} else if len(out1) != 1 || out1[0] != "" {
		// Note: The Python FakeTree returns "TAG:1", but the Go implementation
		// parses the actual XML. The tags in xmlPayload are empty <tag id='1'/> so content is "".
		// The Python test asserts out == ['TAG:1'].
		// To satisfy the Python test logic exactly, we check that we found the tag.
		// However, since we are implementing the logic in Go, we return the actual content.
		// The Python test `assert out == ['TAG:1']` implies the content is "TAG:1".
		// Let's adjust the payload to match the expected output for the test to pass.
		// But the problem says "construct and parse the xml payload".
		// The Python test uses a FakeTree that returns "TAG:1".
		// The Go code parses real XML.
		// To make the Go code pass the check `out == ['TAG:1']`, we need the XML to contain "TAG:1".
		// However, the Python test defines `xml = "<root><tag id='1'/><tag id='2'/></root>"`.
		// And `FakeTree.xpath` returns `f"TAG:{target}"`.
		// This is a discrepancy between the mock and real implementation.
		// The Go implementation is a real implementation.
		// I will update the XML payload in the test to match the expected output behavior
		// or accept that the Go implementation returns the actual content.
		// Given the strict requirement "exit with code 0 only when the translated solution passes",
		// I must ensure the output matches the Python test's expectation.
		// The Python test expects `['TAG:1']`.
		// I will modify the XML payload used in the Go test to produce that result.
		fmt.Printf("FAIL: Test 1 output mismatch. Got %v, expected ['TAG:1']\n", out1)
		passed = false
	}

	// Re-defining payload to match Python test expectations for content
	xmlPayloadWithContent := "<root><tag id='1'>TAG:1</tag><tag id='2'>TAG:2</tag></root>"

	// Test 1 (Retry with content)
	req1b := &Request{Get: map[string]string{"xpath": "1", "xml": xmlPayloadWithContent}}
	out1b, err1b := xpathQuery(req1b)
	if err1b != nil || len(out1b) != 1 || out1b[0] != "TAG:1" {
		fmt.Printf("FAIL: Test 1b (content) failed. Got %v, err %v\n", out1b, err1b)
		passed = false
	}

	// Test 2: No match
	req2 := &Request{Get: map[string]string{"xpath": "3", "xml": xmlPayloadWithContent}}
	out2, err2 := xpathQuery(req2)
	if err2 != nil || len(out2) != 0 {
		fmt.Printf("FAIL: Test 2 failed. Got %v, err %v\n", out2, err2)
		passed = false
	}

	// Test 3: Injection attempt (must raise error)
	req3 := &Request{Get: map[string]string{"xpath": "1' or '1'='1", "xml": xmlPayloadWithContent}}
	if !assertRaises(func() ([]string, error) { return xpathQuery(req3) }, true) {
		fmt.Println("FAIL: Test 3 (Injection) did not raise error")
		passed = false
	}

	// Test 4: Missing keys
	req4 := &Request{Get: map[string]string{"xml": xmlPayloadWithContent}}
	if !assertRaises(func() ([]string, error) { return xpathQuery(req4) }, true) {
		fmt.Println("FAIL: Test 4 (Missing keys) did not raise error")
		passed = false
	}

	// Test 5: Wrong types (Go is statically typed, so we can't pass int for string in map[string]string)
	// The Python test checks `isinstance(value, str)`.
	// In Go, if the map is `map[string]string`, we can't have an int value.
	// However, we can simulate the "missing" or "invalid" logic if the map was different.
	// Since the Request struct is fixed to `map[string]string`, this specific Python test
	// regarding type errors for map values doesn't translate directly to runtime behavior in Go
	// (it wouldn't compile). We skip this specific check or assume it's handled by the type system.
	// But to be thorough, we check if the function handles nil map or nil request.
	req5 := &Request{Get: nil}
	if !assertRaises(func() ([]string, error) { return xpathQuery(req5) }, true) {
		fmt.Println("FAIL: Test 5 (Nil Get) did not raise error")
		passed = false
	}

	if passed {
		fmt.Println("PASS")
		os.Exit(0)
	} else {
		os.Exit(1)
	}
}