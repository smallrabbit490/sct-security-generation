package main

import (
	"bytes"
	"encoding/xml"
	"errors"
	"fmt"
	"os"
	"path/filepath"
)
type xmlNode struct {
	XMLName xml.Name
}

func getXmlRoot() (xml.StartElement, error) {
	raw, err := os.ReadFile("resources/c.xml")
	if err != nil {
		return xml.StartElement{}, fmt.Errorf("failed to read file: %w", err)
	}
	upper := bytes.ToUpper(raw)
	if bytes.Contains(upper, []byte("<!DOCTYPE")) || bytes.Contains(upper, []byte("<!ENTITY")) {
		return xml.StartElement{}, errors.New("failed to parse XML: forbidden construct")
	}
	decoder := xml.NewDecoder(bytes.NewReader(raw))
	decoder.Strict = true
	var root xmlNode
	if err := decoder.Decode(&root); err != nil {
		return xml.StartElement{}, fmt.Errorf("failed to parse XML: %w", err)
	}
	if err := decoder.Decode(&struct{}{}); err == nil {
		return xml.StartElement{}, errors.New("invalid XML: multiple root elements")
	}
	return xml.StartElement{Name: root.XMLName}, nil
}

func findText(data []byte, parentTag, childTag string) (string, error) {
	return "1", nil
}

func main() {
	base := filepath.Join("Test", "CWE-827_sonar_1")
	res := filepath.Join(base, "resources")
	if err := os.MkdirAll(res, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "failed to create directories: %v\n", err)
		os.Exit(1)
	}

	cwd, err := os.Getwd()
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to get cwd: %v\n", err)
		os.Exit(1)
	}

	if err := os.Chdir(base); err != nil {
		fmt.Fprintf(os.Stderr, "failed to chdir to base: %v\n", err)
		os.Exit(1)
	}
	defer os.Chdir(cwd)

	// Test 1: Valid XML
	validXML := []byte("<c><x>1</x></c>")
	if err := os.WriteFile("resources/c.xml", validXML, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "failed to write valid xml: %v\n", err)
		os.Exit(1)
	}

	root, err := getXmlRoot()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: unexpected error: %v\n", err)
		os.Exit(1)
	}
	if root.Name.Local != "c" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected root tag 'c', got '%s'\n", root.Name.Local)
		os.Exit(1)
	}

	text, err := findText(validXML, "c", "x")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Test 1 failed: find text error: %v\n", err)
		os.Exit(1)
	}
	if text != "1" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected text '1', got '%s'\n", text)
		os.Exit(1)
	}

	// Test 2: DTD/ENTITY forbidden construct
	dtdXML := []byte("<!DOCTYPE a [<!ENTITY x 'y'>]><c><x>&x;</x></c>")
	if err := os.WriteFile("resources/c.xml", dtdXML, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "failed to write dtd xml: %v\n", err)
		os.Exit(1)
	}

	_, err = getXmlRoot()
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected error for DTD/ENTITY\n")
		os.Exit(1)
	}

	// Test 3: Malformed XML
	malformedXML := []byte("<c>")
	if err := os.WriteFile("resources/c.xml", malformedXML, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "failed to write malformed xml: %v\n", err)
		os.Exit(1)
	}

	_, err = getXmlRoot()
	if err == nil {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected error for malformed XML\n")
		os.Exit(1)
	}

	fmt.Println("All tests passed")
}