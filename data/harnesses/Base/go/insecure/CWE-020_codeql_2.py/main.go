package main

import (
	"encoding/base64"
	"encoding/gob"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
)

func profile(w http.ResponseWriter, r *http.Request) {
	rawData := r.URL.Query().Get("data")
	if rawData == "" {
		http.Error(w, "missing data", http.StatusBadRequest)
		return
	}
	data, err := base64.StdEncoding.DecodeString(rawData)
	if err != nil {
		http.Error(w, "invalid base64", http.StatusBadRequest)
		return
	}
	obj := string(data)
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	fmt.Fprint(w, obj)
}

func main() {
	passed := 0
	failed := 0

	// Test 1: base64(JSON dict)
	jsonDict := `{"a":1}`
	payload1 := base64.StdEncoding.EncodeToString([]byte(jsonDict))
	req1 := httptest.NewRequest("GET", "/profile?data="+payload1, nil)
	w1 := httptest.NewRecorder()
	profile(w1, req1)
	if w1.Code == http.StatusOK && w1.Body.String() == jsonDict {
		fmt.Println("Test JSON dict: PASS")
		passed++
	} else {
		fmt.Println("Test JSON dict: FAIL")
		failed++
	}

	// Test 2: base64(JSON list)
	jsonList := "[1,2,3]"
	payload2 := base64.StdEncoding.EncodeToString([]byte(jsonList))
	req2 := httptest.NewRequest("GET", "/profile?data="+payload2, nil)
	w2 := httptest.NewRecorder()
	profile(w2, req2)
	if w2.Code == http.StatusOK && w2.Body.String() == jsonList {
		fmt.Println("Test JSON list: PASS")
		passed++
	} else {
		fmt.Println("Test JSON list: FAIL")
		failed++
	}

	// Test 3: invalid base64 -> 400
	req3 := httptest.NewRequest("GET", "/profile?data=@@@", nil)
	w3 := httptest.NewRecorder()
	profile(w3, req3)
	if w3.Code == http.StatusBadRequest {
		fmt.Println("Test invalid base64: PASS")
		passed++
	} else {
		fmt.Println("Test invalid base64: FAIL")
		failed++
	}

	// Test 4: missing data -> 400
	req4 := httptest.NewRequest("GET", "/profile", nil)
	w4 := httptest.NewRecorder()
	profile(w4, req4)
	if w4.Code == http.StatusBadRequest {
		fmt.Println("Test missing data: PASS")
		passed++
	} else {
		fmt.Println("Test missing data: FAIL")
		failed++
	}

	// Test 5: decoded is not JSON -> 200 (insecure behavior: treats arbitrary bytes as string)
	notJSON := "not-json"
	payload5 := base64.StdEncoding.EncodeToString([]byte(notJSON))
	req5 := httptest.NewRequest("GET", "/profile?data="+payload5, nil)
	w5 := httptest.NewRecorder()
	profile(w5, req5)
	if w5.Code == http.StatusOK && w5.Body.String() == notJSON {
		fmt.Println("Test not JSON: PASS")
		passed++
	} else {
		fmt.Println("Test not JSON: FAIL")
		failed++
	}

	// Test 6: gob payload -> 200 (insecure behavior: accepts arbitrary deserialization payload)
	var gobBuf []byte
	gobEnc := gob.NewEncoder(&writeBuffer{&gobBuf})
	gobEnc.Encode(map[string]interface{}{"p": 1})
	payload6 := base64.StdEncoding.EncodeToString(gobBuf)
	req6 := httptest.NewRequest("GET", "/profile?data="+payload6, nil)
	w6 := httptest.NewRecorder()
	profile(w6, req6)
	if w6.Code == http.StatusOK {
		fmt.Println("Test gob payload: PASS")
		passed++
	} else {
		fmt.Printf("Test gob payload: FAIL (expected 200, got %d)\n", w6.Code)
		failed++
	}

	fmt.Printf("\nPassed: %d, Failed: %d\n", passed, failed)
	if failed > 0 {
		os.Exit(1)
	}
	os.Exit(0)
}

type writeBuffer struct {
	buf *[]byte
}

func (wb *writeBuffer) Write(p []byte) (n int, err error) {
	*wb.buf = append(*wb.buf, p...)
	return len(p), nil
}

// Ensure json and gob are referenced
var _ = json.Marshal
var _ = gob.NewEncoder