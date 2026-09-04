package main

import (
	"bytes"
	"encoding/xml"
	"errors"
	"fmt"
	"os"
)
var requestData []byte

type safeXMLNode struct {
	XMLName xml.Name
	Inner   []byte `xml:",innerxml"`
}

func upload() []byte {
	if requestData == nil {
		panic(errors.New("type error"))
	}
	b := make([]byte, len(requestData))
	copy(b, requestData)
	upper := bytes.ToUpper(b)
	if bytes.Contains(upper, []byte("<!DOCTYPE")) || bytes.Contains(upper, []byte("<!ENTITY")) {
		panic(errors.New("value error"))
	}
	decoder := xml.NewDecoder(bytes.NewReader(b))
	decoder.Strict = true
	var root safeXMLNode
	if err := decoder.Decode(&root); err != nil {
		panic(errors.New("value error"))
	}
	if err := decoder.Decode(&struct{}{}); err == nil {
		panic(errors.New("value error"))
	}
	out, err := xml.Marshal(root)
	if err != nil {
		panic(errors.New("value error"))
	}
	return out
}

func assertPanics(fn func(), expectedMsg string) {
	defer func() {
		r := recover()
		if r == nil {
			fmt.Fprintf(os.Stderr, "expected panic with message %q but did not panic\n", expectedMsg)
			os.Exit(1)
		}
		err, ok := r.(error)
		if !ok || err.Error() != expectedMsg {
			fmt.Fprintf(os.Stderr, "expected panic with message %q but got %v\n", expectedMsg, r)
			os.Exit(1)
		}
	}()
	fn()
}

func main() {
	// Test 1: Good XML
	good := []byte("<a><b>1</b></a>")
	requestData = good
	out := upload()
	if !bytes.Contains(out, []byte("<b>1</b>")) {
		fmt.Fprintln(os.Stderr, "good xml test failed: missing <b>1</b>")
		os.Exit(1)
	}

	// Test 2: DTD must be rejected
	dtd := []byte("<!DOCTYPE a [<!ENTITY x 'y'>]><a>&x;</a>")
	requestData = dtd
	assertPanics(func() { upload() }, "value error")

	// Test 3: Invalid XML rejected
	bad := []byte("<a><b></a>")
	requestData = bad
	assertPanics(func() { upload() }, "value error")

	// Test 4: Wrong type (nil request data) rejected
	requestData = nil
	assertPanics(func() { upload() }, "type error")

	fmt.Println("all tests passed")
}