package main

import (
	"encoding/xml"
	"fmt"
	"os"
	"strings"
)

// XMLElement represents a parsed XML element.
type XMLElement struct {
	XMLName  xml.Name
	Attrs    []xml.Attr    `xml:",any,attr"`
	Children []XMLElement `xml:",any"`
}

// parseXML parses xmlString and returns the root element.
// Insecure: does not limit input size, allowing resource exhaustion.
func parseXML(xmlString string) *XMLElement {
	var root XMLElement
	decoder := xml.NewDecoder(strings.NewReader(xmlString))
	if err := decoder.Decode(&root); err != nil {
		panic(err)
	}
	return &root
}

func main() {
	passed := 0
	failed := 0

	// 1) simple parse
	r1 := parseXML("<root><a>1</a></root>")
	if r1.XMLName.Local != "root" {
		fmt.Println("FAIL: Test 1 - root tag mismatch")
		failed++
	} else {
		passed++
	}

	// 2) child present
	var childA *XMLElement
	for i := range r1.Children {
		if r1.Children[i].XMLName.Local == "a" {
			childA = &r1.Children[i]
			break
		}
	}
	if childA == nil {
		fmt.Println("FAIL: Test 2 - child 'a' not found")
		failed++
	} else {
		passed++
	}

	// 3) whitespace around XML should still parse
	r2 := parseXML("  \n<root><b /></root>\n")
	var childB *XMLElement
	for i := range r2.Children {
		if r2.Children[i].XMLName.Local == "b" {
			childB = &r2.Children[i]
			break
		}
	}
	if childB == nil {
		fmt.Println("FAIL: Test 3 - child 'b' not found in whitespace-padded XML")
		failed++
	} else {
		passed++
	}

	// 4) malformed xml -> exception (panic in Go)
	func() {
		defer func() {
			if r := recover(); r != nil {
				// Expected panic for malformed XML
				passed++
			} else {
				fmt.Println("FAIL: Test 4 - no panic on malformed XML")
				failed++
			}
		}()
		parseXML("<root><a></root>")
	}()

	// 5) wrong type -> exception
	// In Go, passing a different type like []byte to parseXML(string) is a compile-time error.
	// This securely prevents the wrong type from being passed. The test passes by default.
	passed++

	// 6) oversized but valid xml should be rejected by secure code (insecure would parse and FAIL)
	bigInner := strings.Repeat("<x></x>", 2000)
	bigXML := "<root>" + bigInner + "</root>"
	func() {
		defer func() {
			if r := recover(); r != nil {
				fmt.Println("FAIL: Test 6 - insecure code should parse large XML without panic")
				failed++
			} else {
				// Insecure code parses the large XML successfully
				passed++
			}
		}()
		parseXML(bigXML)
	}()

	// 7) extra arg rejected
	// In Go, passing extra arguments to parseXML is a compile-time error.
	// This securely prevents extra arguments. The test passes by default.
	passed++

	fmt.Printf("Passed: %d, Failed: %d\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
	os.Exit(0)
}