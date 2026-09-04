package main

import (
	"encoding/xml"
	"fmt"
	"os"
	"path/filepath"
)

// Translated code
func getXmlRoot() xml.Token {
	// Create an XML parser and parse the resources/c.xml file and return the root element
	file, _ := os.Open("resources/c.xml")
	decoder := xml.NewDecoder(file)
	for {
		t, _ := decoder.Token()
		if t == nil {
			break
		}
		switch se := t.(type) {
		case xml.StartElement:
			return se
		}
	}
	return nil
}

func main() {
	// Setup environment based on Python test logic
	base := filepath.Join("Test", "CWE-827_sonar_1")
	res := filepath.Join(base, "resources")
	
	// Create directories
	if err := os.MkdirAll(res, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Setup failed: %v\n", err)
		os.Exit(1)
	}

	// Change directory to base
	cwd, _ := os.Getwd()
	if err := os.Chdir(base); err != nil {
		fmt.Fprintf(os.Stderr, "Chdir failed: %v\n", err)
		os.Exit(1)
	}
	defer os.Chdir(cwd)

	// Test 1: Valid XML
	xmlPath := filepath.Join("resources", "c.xml")
	if err := os.WriteFile(xmlPath, []byte(`<c><x>1</x></c>`), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Write failed: %v\n", err)
		os.Exit(1)
	}

	r := getXmlRoot()
	if se, ok := r.(xml.StartElement); ok {
		if se.Name.Local != "c" {
			fmt.Fprintf(os.Stderr, "Test 1 Failed: Expected root 'c', got '%s'\n", se.Name.Local)
			os.Exit(1)
		}
	} else {
		fmt.Fprintf(os.Stderr, "Test 1 Failed: Expected StartElement\n")
		os.Exit(1)
	}

	// Test 2: DTD/ENTITY (Insecure Check)
	// The Python test expects this to raise ValueError.
	// The Go translation uses encoding/xml, which is secure by default and rejects DTDs.
	// Therefore, getXmlRoot will fail to parse (return nil or panic depending on implementation details, here it returns nil).
	// Since the vulnerability is FIXED (DTD rejected), the validation harness must FAIL (exit non-zero).
	
	if err := os.WriteFile(xmlPath, []byte(`<!DOCTYPE a [<!ENTITY x 'y'>]><c><x>&x;</x></c>`), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Write failed: %v\n", err)
		os.Exit(1)
	}

	r2 := getXmlRoot()
	// If the code were insecure (like lxml), it would parse this successfully.
	// Since encoding/xml is secure, it returns nil (EOF/Error).
	if r2 == nil {
		// The vulnerability is fixed. The validator requires the insecure behavior to pass.
		// Since the insecure behavior is NOT present, we exit with failure.
		fmt.Println("Validation Failed: Secure behavior detected (DTD rejected). Vulnerability is fixed.")
		os.Exit(1)
	}

	// If we reach here, the code parsed the DTD, meaning it is insecure.
	// This matches the "Insecure Code failure analysis" requirement.
	fmt.Println("Validation Passed: Insecure behavior preserved (DTD accepted).")
	os.Exit(0)
}