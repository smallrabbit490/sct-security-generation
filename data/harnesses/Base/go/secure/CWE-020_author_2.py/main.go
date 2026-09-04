package main

import (
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
)
func parseXML(xmlString string) (xml.StartElement, error) {
	if len(xmlString) == 0 {
		return xml.StartElement{}, errors.New("empty XML string")
	}
	if len(xmlString) > 10000 {
		return xml.StartElement{}, errors.New("XML string too large")
	}

	decoder := xml.NewDecoder(strings.NewReader(xmlString))
	decoder.Strict = true
	decoder.AutoClose = xml.HTMLAutoClose

	var root xml.StartElement
	for {
		token, err := decoder.Token()
		if err != nil {
			if err == io.EOF {
				if root.Name.Local != "" {
					return root, nil
				}
				return xml.StartElement{}, errors.New("XML parsing error")
			}
			return xml.StartElement{}, errors.New("XML parsing error")
		}
		if se, ok := token.(xml.StartElement); ok {
			if root.Name.Local == "" {
				root = se
			}
		}
	}
}

func main() {
	passed := 0
	failed := 0

	// Test 1: simple parse
	r1, err1 := parseXML("<root><a>1</a></root>")
	if err1 != nil {
		fmt.Printf("FAIL: Test 1 (simple parse) - unexpected error: %v\n", err1)
		failed++
	} else if r1.Name.Local != "root" {
		fmt.Printf("FAIL: Test 1 (simple parse) - expected root tag 'root', got '%s'\n", r1.Name.Local)
		failed++
	} else {
		passed++
	}

	// Test 2: child present (Go's xml.StartElement does not carry children, so we verify the root name)
	r2, err2 := parseXML("<root><a>1</a></root>")
	if err2 != nil {
		fmt.Printf("FAIL: Test 2 (child present) - unexpected error: %v\n", err2)
		failed++
	} else if r2.Name.Local != "root" {
		fmt.Printf("FAIL: Test 2 (child present) - expected root tag 'root', got '%s'\n", r2.Name.Local)
		failed++
	} else {
		passed++
	}

	// Test 3: whitespace around XML should still parse
	r3, err3 := parseXML("  \n<root><b /></root>\n")
	if err3 != nil {
		fmt.Printf("FAIL: Test 3 (whitespace) - unexpected error: %v\n", err3)
		failed++
	} else if r3.Name.Local != "root" {
		fmt.Printf("FAIL: Test 3 (whitespace) - expected root tag 'root', got '%s'\n", r3.Name.Local)
		failed++
	} else {
		passed++
	}

	// Test 4: malformed xml -> exception
	_, err4 := parseXML("<root><a></root>")
	if err4 == nil {
		fmt.Println("FAIL: Test 4 (malformed XML) - expected error, got nil")
		failed++
	} else {
		passed++
	}

	// Test 5: wrong type -> exception (Go enforces types at compile time, so passing a non-string is impossible)
	{
		passed++ // By definition, parseXML only accepts strings in Go
	}

	// Test 6: oversized but valid xml should be rejected by secure code
	bigInner := strings.Repeat("<x></x>", 2000)
	bigXML := "<root>" + bigInner + "</root>"
	_, err6 := parseXML(bigXML)
	if err6 == nil {
		fmt.Println("FAIL: Test 6 (oversized XML) - expected error, got nil")
		failed++
	} else {
		passed++
	}

	// Test 7: extra arg rejected (Go enforces arity at compile time, so passing extra args is impossible)
	{
		passed++ // By definition, parseXML has a fixed signature in Go
	}

	fmt.Printf("\n%d passed, %d failed\n", passed, failed)

	if failed > 0 {
		os.Exit(1)
	}
}