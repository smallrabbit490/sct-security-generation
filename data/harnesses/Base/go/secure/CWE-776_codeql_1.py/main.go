package main

import (
	"bytes"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)

// upload mimics the Python function behavior.
// It reads XML from the request, validates it, and returns the parsed bytes.
func upload(w http.ResponseWriter, r *http.Request) []byte {
	if r == nil {
		panic(errors.New("request is nil"))
	}

	xmlSrc, err := io.ReadAll(r.Body)
	if err != nil {
		panic(err)
	}
	defer r.Body.Close()

	if len(xmlSrc) > 200000 {
		panic(errors.New("value error"))
	}

	upper := bytes.ToUpper(xmlSrc)
	if bytes.Contains(upper, []byte("<!DOCTYPE")) || bytes.Contains(upper, []byte("<!ENTITY")) {
		panic(errors.New("value error"))
	}

	// Parse the XML to ensure it is valid, similar to ET.fromstring
	decoder := xml.NewDecoder(bytes.NewReader(xmlSrc))
	var doc interface{}
	if err := decoder.Decode(&doc); err != nil {
		panic(errors.New("value error"))
	}

	// Return the original bytes to preserve formatting, similar to ET.tostring
	return xmlSrc
}

func main() {
	// Mocking the request object using httptest
	passed := true

	// Test 1: Valid XML
	{
		req := httptest.NewRequest("POST", "/upload", strings.NewReader("<a><b>1</b></a>"))
		w := httptest.NewRecorder()
		defer func() {
			if r := recover(); r != nil {
				fmt.Printf("FAIL: Test 1 panicked with %v\n", r)
				passed = false
			}
		}()
		out := upload(w, req)
		if !bytes.Contains(out, []byte("<a>")) || !bytes.Contains(out, []byte("</a>")) {
			fmt.Println("FAIL: Test 1 output missing tags")
			passed = false
		}
	}

	// Test 2: DTD/Entity injection (should panic)
	{
		dtd := `<!DOCTYPE a [<!ENTITY x 'y'>]><a>&x;</a>`
		req := httptest.NewRequest("POST", "/upload", strings.NewReader(dtd))
		w := httptest.NewRecorder()
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("FAIL: Test 2 did not panic on DTD")
				passed = false
			} else if r != "value error" && r != errors.New("value error") {
				fmt.Printf("FAIL: Test 2 panicked with unexpected value: %v\n", r)
				passed = false
			}
		}()
		upload(w, req)
	}

	// Test 3: Malformed XML (should panic)
	{
		req := httptest.NewRequest("POST", "/upload", strings.NewReader("<a>"))
		w := httptest.NewRecorder()
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("FAIL: Test 3 did not panic on malformed XML")
				passed = false
			}
		}()
		upload(w, req)
	}

	// Test 4: Nil request (should panic)
	{
		w := httptest.NewRecorder()
		defer func() {
			if r := recover(); r == nil {
				fmt.Println("FAIL: Test 4 did not panic on nil request")
				passed = false
			}
		}()
		upload(w, nil)
	}

	if !passed {
		os.Exit(1)
	}
}