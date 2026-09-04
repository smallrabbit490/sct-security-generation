package main

import (
	"bytes"
	"encoding/xml"
	"errors"
	"fmt"
	"os"
	"path/filepath"
)
func getRoot() (xml.Name, error) {
	path := "resources/config.xml"

	raw, err := os.ReadFile(path)
	if err != nil {
		return xml.Name{}, errors.New("failed to read file")
	}

	upper := bytes.ToUpper(raw)
	if bytes.Contains(upper, []byte("<!DOCTYPE")) || bytes.Contains(upper, []byte("<!ENTITY")) {
		return xml.Name{}, errors.New("forbidden DTD or ENTITY found")
	}

	decoder := xml.NewDecoder(bytes.NewReader(raw))
	decoder.Strict = true
	decoder.AutoClose = nil
	decoder.Entity = nil

	var root xml.Name
	foundRoot := false
	for {
		token, err := decoder.Token()
		if err != nil {
			return xml.Name{}, errors.New("failed to parse XML")
		}

		if se, ok := token.(xml.StartElement); ok {
			root = se.Name
			foundRoot = true
			break
		}
	}

	if !foundRoot {
		return xml.Name{}, errors.New("no root element found")
	}

	// Drain remaining tokens to ensure the entire XML is well-formed
	for {
		_, err := decoder.Token()
		if err != nil {
			if err.Error() == "EOF" {
				break
			}
			return xml.Name{}, errors.New("failed to parse XML")
		}
	}

	return root, nil
}

func main() {
	base := filepath.Join("Test", "CWE-611_sonar_1")
	resdir := filepath.Join(base, "resources")
	err := os.MkdirAll(resdir, 0755)
	if err != nil {
		fmt.Println("Setup error:", err)
		os.Exit(1)
	}

	passed := 0
	failed := 0

	// Test 1: Safe XML
	safe := []byte("<config><name>ok</name></config>")
	err = os.WriteFile(filepath.Join(resdir, "config.xml"), safe, 0644)
	if err != nil {
		fmt.Println("Test 1 setup error:", err)
		os.Exit(1)
	}

	cwd, err := os.Getwd()
	if err != nil {
		fmt.Println("Getwd error:", err)
		os.Exit(1)
	}
	err = os.Chdir(base)
	if err != nil {
		fmt.Println("Chdir error:", err)
		os.Exit(1)
	}

	root, err := getRoot()
	if err != nil {
		fmt.Println("Test 1 failed: unexpected error:", err)
		failed++
	} else if root.Local != "config" {
		fmt.Printf("Test 1 failed: expected root 'config', got '%s'\n", root.Local)
		failed++
	} else {
		fmt.Println("Test 1 passed")
		passed++
	}

	// Test 2: DTD/ENTITY injection
	dtd := []byte("<!DOCTYPE a [<!ENTITY x 'y'>]><config><name>&x;</name></config>")
	err = os.WriteFile(filepath.Join("resources", "config.xml"), dtd, 0644)
	if err != nil {
		fmt.Println("Test 2 setup error:", err)
		os.Exit(1)
	}

	_, err = getRoot()
	if err != nil {
		fmt.Println("Test 2 passed")
		passed++
	} else {
		fmt.Println("Test 2 failed: expected error for DTD/ENTITY")
		failed++
	}

	// Test 3: Malformed XML
	malformed := []byte("<config><name></config>")
	err = os.WriteFile(filepath.Join("resources", "config.xml"), malformed, 0644)
	if err != nil {
		fmt.Println("Test 3 setup error:", err)
		os.Exit(1)
	}

	_, err = getRoot()
	if err != nil {
		fmt.Println("Test 3 passed")
		passed++
	} else {
		fmt.Println("Test 3 failed: expected error for malformed XML")
		failed++
	}

	err = os.Chdir(cwd)
	if err != nil {
		fmt.Println("Chdir back error:", err)
		os.Exit(1)
	}

	fmt.Printf("\n%d passed, %d failed\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
}