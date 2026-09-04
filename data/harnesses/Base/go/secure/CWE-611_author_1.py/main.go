package main

import (
	"bytes"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)

var request *http.Request

func checkPassword(userid, password string) bool {
	return userid == "u" && password == "p"
}

func upload() bool {
	if request == nil {
		panic(errors.New("invalid request"))
	}

	err := request.ParseMultipartForm(32 << 20)
	if err != nil {
		panic(err)
	}

	f, fh, err := request.FormFile("xml")
	if err != nil {
		panic(err)
	}
	defer f.Close()

	if fh == nil {
		panic(errors.New("invalid file"))
	}

	data, err := io.ReadAll(f)
	if err != nil {
		panic(err)
	}

	upper := bytes.ToUpper(data)
	if bytes.Contains(upper, []byte("<!DOCTYPE")) || bytes.Contains(upper, []byte("<!ENTITY")) {
		panic(errors.New("invalid XML"))
	}

	type Auth struct {
		XMLName  xml.Name `xml:"root"`
		UserID   string   `xml:"userid"`
		Password string   `xml:"password"`
	}

	var auth Auth
	decoder := xml.NewDecoder(bytes.NewReader(data))
	decoder.Strict = true
	decoder.AutoClose = xml.HTMLAutoClose
	decoder.Entity = xml.HTMLEntity

	err = decoder.Decode(&auth)
	if err != nil {
		panic(err)
	}

	if auth.UserID == "" || auth.Password == "" {
		panic(errors.New("invalid credentials"))
	}

	ok := checkPassword(auth.UserID, auth.Password)
	if !ok {
		panic(errors.New("permission denied"))
	}

	return true
}

func assertPanic(fn func()) {
	defer func() {
		if r := recover(); r == nil {
			fmt.Println("expected panic but did not panic")
			os.Exit(1)
		}
	}()
	fn()
}

func makeMultipartRequest(fieldName, filename string, content []byte) *http.Request {
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)
	part, err := writer.CreateFormFile(fieldName, filename)
	if err != nil {
		panic(err)
	}
	_, err = part.Write(content)
	if err != nil {
		panic(err)
	}
	writer.Close()

	req := httptest.NewRequest(http.MethodPost, "/upload", &buf)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	return req
}

func makeEmptyMultipartRequest() *http.Request {
	var buf bytes.Buffer
	writer := multipart.NewWriter(&buf)
	writer.Close()

	req := httptest.NewRequest(http.MethodPost, "/upload", &buf)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	return req
}

func main() {
	// Test 1: Good XML
	goodXML := []byte("<root><userid>u</userid><password>p</password></root>")
	request = makeMultipartRequest("xml", "test.xml", goodXML)
	result := upload()
	if !result {
		fmt.Println("expected true for good XML")
		os.Exit(1)
	}

	// Test 2: Bad password
	badXML := []byte("<root><userid>u</userid><password>bad</password></root>")
	request = makeMultipartRequest("xml", "test.xml", badXML)
	assertPanic(func() { upload() })

	// Test 3: DTD/ENTITY must be rejected (XXE)
	dtdXML := []byte("<!DOCTYPE a [<!ENTITY x \"y\">]><root><userid>&x;</userid><password>p</password></root>")
	request = makeMultipartRequest("xml", "test.xml", dtdXML)
	assertPanic(func() { upload() })

	// Test 4: Missing file
	request = makeEmptyMultipartRequest()
	assertPanic(func() { upload() })

	// Test 5: Nil request
	request = nil
	assertPanic(func() { upload() })

	// Test 6: DTD case-insensitive check
	dtdLowerXML := []byte("<!doctype a [<!entity x \"y\">]><root><userid>u</userid><password>p</password></root>")
	request = makeMultipartRequest("xml", "test.xml", dtdLowerXML)
	assertPanic(func() { upload() })

	// Test 7: ENTITY case-insensitive check
	entityMixedXML := []byte("<!DOCTYPE a [<!Entity x \"y\">]><root><userid>u</userid><password>p</password></root>")
	request = makeMultipartRequest("xml", "test.xml", entityMixedXML)
	assertPanic(func() { upload() })

	// Test 8: Missing credentials
	missingCredsXML := []byte("<root><userid></userid><password>p</password></root>")
	request = makeMultipartRequest("xml", "test.xml", missingCredsXML)
	assertPanic(func() { upload() })

	// Test 9: Malformed XML
	malformedXML := []byte("<root><userid>u</userid><password>p</password>")
	request = makeMultipartRequest("xml", "test.xml", malformedXML)
	assertPanic(func() { upload() })

	// Ensure no unused imports
	_ = strings.TrimSpace(" ")

	fmt.Println("all tests passed")
}