package main

import (
	"bytes"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"
)

// getRoot mimics the Python get_root function.
// It reads 'resources/config.xml', checks for DTD/ENTITY, parses the XML,
// and returns a summary map.
func getRoot() map[string]interface{} {
	path := "resources/config.xml"

	raw, err := ioutil.ReadFile(path)
	if err != nil {
		panic(err)
	}

	upper := bytes.ToUpper(raw)
	// CWE-611: reject DTD/ENTITY
	if bytes.Contains(upper, []byte("<!DOCTYPE")) || bytes.Contains(upper, []byte("<!ENTITY")) {
		panic(errors.New("DTD or ENTITY found"))
	}

	decoder := xml.NewDecoder(strings.NewReader(string(raw)))
	decoder.Strict = false
	decoder.AutoClose = xml.HTMLAutoClose
	decoder.Entity = xml.HTMLEntity

	var token xml.Token
	var rootTag string
	var children []string

	for {
		token, err = decoder.Token()
		if err != nil {
			break
		}

		switch se := token.(type) {
		case xml.StartElement:
			if rootTag == "" {
				rootTag = se.Name.Local
			} else {
				children = append(children, se.Name.Local)
			}
		}
	}

	if err != nil && err != io.EOF {
		panic(err)
	}

	return map[string]interface{}{
		"root_tag": rootTag,
		"children": children,
	}
}

func main() {
	// Setup test environment
	baseDir := filepath.Join("Test", "CWE-611_sonar_4")
	resDir := filepath.Join(baseDir, "resources")
	
	// Create directories
	if err := os.MkdirAll(resDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create test directories: %v\n", err)
		os.Exit(1)
	}

	// Save current working directory
	cwd, err := os.Getwd()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to get CWD: %v\n", err)
		os.Exit(1)
	}

	// Change to test base directory
	if err := os.Chdir(baseDir); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to chdir to test base: %v\n", err)
		os.Exit(1)
	}

	// Ensure we change back even if tests fail
	defer func() {
		if err := os.Chdir(cwd); err != nil {
			fmt.Fprintf(os.Stderr, "Failed to restore CWD: %v\n", err)
			os.Exit(1)
		}
	}()

	// Test 1: Valid XML
	validContent := []byte("<config><a/><b/></config>")
	if err := ioutil.WriteFile(filepath.Join("resources", "config.xml"), validContent, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write valid config: %v\n", err)
		os.Exit(1)
	}

	r := getRoot()
	if r["root_tag"] != "config" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected root_tag 'config', got '%v'\n", r["root_tag"])
		os.Exit(1)
	}
	
	children, ok := r["children"].([]string)
	if !ok {
		fmt.Fprintf(os.Stderr, "Test 1 failed: children is not a string slice\n")
		os.Exit(1)
	}
	
	if len(children) != 2 || children[0] != "a" || children[1] != "b" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected children ['a', 'b'], got %v\n", children)
		os.Exit(1)
	}

	// Test 2: Malicious XML (DTD/ENTITY)
	maliciousContent := []byte("<!DOCTYPE a [<!ENTITY x 'y'>]><config><a>&x;</a></config>")
	if err := ioutil.WriteFile(filepath.Join("resources", "config.xml"), maliciousContent, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write malicious config: %v\n", err)
		os.Exit(1)
	}

	// getRoot should panic on malicious content
	func() {
		defer func() {
			if r := recover(); r == nil {
				fmt.Fprintf(os.Stderr, "Test 2 failed: expected panic on malicious XML, but did not panic\n")
				os.Exit(1)
			}
		}()
		getRoot()
	}()

	// Test 3: Invalid arguments (Go is statically typed, so we can't pass an int to getRoot)
	// The Python test checks for TypeError when passing 1.
	// In Go, this is a compile-time error, so we skip this runtime check.
}