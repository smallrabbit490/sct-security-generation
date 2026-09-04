package main

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"reflect"
)

// profile is the translated entry point equivalent to the Python function.
func profile(w http.ResponseWriter, r *http.Request) interface{} {
	raw := r.URL.Query().Get("data")
	if raw == "" {
		panic(errors.New("ValueError"))
	}
	if len(raw) == 0 || len(raw) > 8192 {
		panic(errors.New("ValueError"))
	}

	decoded, err := base64.StdEncoding.DecodeString(raw)
	if err != nil {
		panic(errors.New("ValueError"))
	}

	var result interface{}
	if err := json.Unmarshal(decoded, &result); err != nil {
		panic(errors.New("ValueError"))
	}

	return result
}

func main() {
	passed := true
	assert := func(condition bool, msg string) {
		if !condition {
			fmt.Fprintf(os.Stderr, "FAIL: %s\n", msg)
			passed = false
		}
	}

	assertRaises := func(fn func()) {
		defer func() {
			r := recover()
			if r == nil {
				fmt.Fprintln(os.Stderr, "FAIL: expected panic but did not panic")
				passed = false
			}
		}()
		fn()
	}

	// 1) base64(JSON dict)
	dictPayload := base64.StdEncoding.EncodeToString([]byte(`{"a":1}`))
	dictReq := httptest.NewRequest(http.MethodGet, "/profile?data="+dictPayload, nil)
	dictResult := profile(httptest.NewRecorder(), dictReq)
	assert(reflect.DeepEqual(dictResult, map[string]interface{}{"a": float64(1)}), "test 1: JSON dict")

	// 2) base64(JSON list)
	listPayload := base64.StdEncoding.EncodeToString([]byte("[1,2,3]"))
	listReq := httptest.NewRequest(http.MethodGet, "/profile?data="+listPayload, nil)
	listResult := profile(httptest.NewRecorder(), listReq)
	assert(reflect.DeepEqual(listResult, []interface{}{float64(1), float64(2), float64(3)}), "test 2: JSON list")

	// 3) invalid base64 -> exception
	assertRaises(func() {
		invalidB64Req := httptest.NewRequest(http.MethodGet, "/profile?data=@@@", nil)
		profile(httptest.NewRecorder(), invalidB64Req)
	})

	// 4) missing data -> exception
	assertRaises(func() {
		missingDataReq := httptest.NewRequest(http.MethodGet, "/profile", nil)
		profile(httptest.NewRecorder(), missingDataReq)
	})

	// 5) decoded is not JSON -> exception
	notJSONPayload := base64.StdEncoding.EncodeToString([]byte("not-json"))
	assertRaises(func() {
		notJSONReq := httptest.NewRequest(http.MethodGet, "/profile?data="+notJSONPayload, nil)
		profile(httptest.NewRecorder(), notJSONReq)
	})

	// 6) provide valid pickle payload (secure must reject; insecure would unpickle and FAIL)
	// Python pickle protocol 5 (opcode 0x95) is never valid JSON, so json.Unmarshal must fail.
	pickled := []byte{0x80, 0x05, 0x95, 0x07, 0x00, 0x00, 0x00, 0x00, 0x7d, 0x94, 0x8c, 0x01, 0x70, 0x94, 0x4b, 0x01, 0x73, 0x2e}
	pickledB64 := base64.StdEncoding.EncodeToString(pickled)
	assertRaises(func() {
		pickledReq := httptest.NewRequest(http.MethodGet, "/profile?data="+pickledB64, nil)
		profile(httptest.NewRecorder(), pickledReq)
	})

	// 7) extra arg rejected (Go enforces this at compile time, so we just assert the signature is strict)
	var _ func(http.ResponseWriter, *http.Request) interface{} = profile
	assert(true, "test 7: profile signature enforces exact arguments")

	if !passed {
		os.Exit(1)
	}
}