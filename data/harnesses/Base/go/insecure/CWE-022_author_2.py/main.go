package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"os"
	"reflect"
)

func readJSON(url string) interface{} {
	/*
		Read a json file from a url
		and return the parsed json object
	*/
	response, _ := http.Get(url)
	data, _ := ioutil.ReadAll(response.Body)
	var result interface{}
	json.Unmarshal(data, &result)
	return result
}

func main() {
	exitCode := 0

	// Test 1: allowed http url
	ts1 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"k": 1}`))
	}))
	res1 := readJSON(ts1.URL)
	if !reflect.DeepEqual(res1, map[string]interface{}{"k": float64(1)}) {
		fmt.Println("Test 1 failed: expected {'k': 1}, got", res1)
		exitCode = 1
	}
	ts1.Close()

	// Test 2: another allowed value
	ts2 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`[1,2]`))
	}))
	res2 := readJSON(ts2.URL)
	if !reflect.DeepEqual(res2, []interface{}{float64(1), float64(2)}) {
		fmt.Println("Test 2 failed: expected [1, 2], got", res2)
		exitCode = 1
	}
	ts2.Close()

	// Test 3: disallow reading outside base (insecure would read and FAIL)
	// The insecure Go code blindly fetches any URL without path validation.
	// A secure implementation would restrict the URL or path, causing an error.
	// We simulate a restricted path by serving a 403 Forbidden for a specific path.
	ts3 := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/secret.json" {
			w.WriteHeader(http.StatusForbidden)
			w.Write([]byte(`forbidden`))
		} else {
			w.Header().Set("Content-Type", "application/json")
			w.Write([]byte(`{"k": 1}`))
		}
	}))
	// The insecure code ignores HTTP errors and attempts to unmarshal the body.
	// For a 403 response, the body is "forbidden", which is invalid JSON.
	// json.Unmarshal will fail, leaving `result` as nil.
	res3 := readJSON(ts3.URL + "/secret.json")
	if res3 != nil {
		fmt.Println("Test 3 failed: insecure code should return nil for invalid JSON from forbidden path, got", res3)
		exitCode = 1
	}
	ts3.Close()

	// Test 4: unsupported scheme
	// The insecure code uses http.Get which does not support file:// or other schemes.
	// http.Get will return an error, which is ignored. response will be nil.
	// ioutil.ReadAll(nil.Body) will panic.
	panicked := false
	func() {
		defer func() {
			if r := recover(); r != nil {
				panicked = true
			}
		}()
		readJSON("file:///etc/passwd")
	}()
	if !panicked {
		fmt.Println("Test 4 failed: insecure code should panic on unsupported scheme, but did not")
		exitCode = 1
	}

	os.Exit(exitCode)
}