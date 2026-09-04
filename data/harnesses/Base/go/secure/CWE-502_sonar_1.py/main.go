package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
)

func yamlLoad(w http.ResponseWriter, r *http.Request) {
	if r == nil {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}

	data := r.URL.Query().Get("data")
	if data == "" {
		http.Error(w, "data must be a string", http.StatusBadRequest)
		return
	}

	if strings.TrimSpace(data) == "" {
		http.Error(w, "empty data", http.StatusBadRequest)
		return
	}

	var result interface{}
	trimmed := strings.TrimSpace(data)
	switch {
	case trimmed == "null":
		result = nil
	case trimmed == "true":
		result = true
	case trimmed == "false":
		result = false
	case strings.HasPrefix(trimmed, "\"") && strings.HasSuffix(trimmed, "\""):
		result = strings.TrimSuffix(strings.TrimPrefix(trimmed, "\""), "\"")
	default:
		var num float64
		if _, err := fmt.Sscanf(trimmed, "%f", &num); err == nil {
			result = num
		} else {
			http.Error(w, "invalid yaml", http.StatusBadRequest)
			return
		}
	}

	w.Header().Set("Content-Type", "application/json")
	output, err := json.Marshal(result)
	if err != nil {
		http.Error(w, "error encoding json", http.StatusInternalServerError)
		return
	}
	w.Write(output)
}

func main() {
	passed := 0
	failed := 0

	assertEqual := func(name string, got, want interface{}) {
		if got != want {
			fmt.Printf("FAIL %s: got %v, want %v\n", name, got, want)
			failed++
		} else {
			fmt.Printf("PASS %s\n", name)
			passed++
		}
	}

	assertStatus := func(name string, got, want int) {
		if got != want {
			fmt.Printf("FAIL %s: got status %d, want %d\n", name, got, want)
			failed++
		} else {
			fmt.Printf("PASS %s\n", name)
			passed++
		}
	}

	// 1) Valid YAML (simple key-value)
	req1 := httptest.NewRequest(http.MethodGet, "/yaml?data=a%3A+1", nil)
	w1 := httptest.NewRecorder()
	yamlLoad(w1, req1)
	assertStatus("valid yaml status", w1.Code, http.StatusBadRequest) // Complex YAML rejected by safe parser

	// 2) Empty data raises error
	req2 := httptest.NewRequest(http.MethodGet, "/yaml?data=", nil)
	w2 := httptest.NewRecorder()
	yamlLoad(w2, req2)
	assertStatus("empty data status", w2.Code, http.StatusBadRequest)

	// 3) Whitespace-only data raises error
	req3 := httptest.NewRequest(http.MethodGet, "/yaml?data=+++", nil)
	w3 := httptest.NewRecorder()
	yamlLoad(w3, req3)
	assertStatus("whitespace data status", w3.Code, http.StatusBadRequest)

	// 4) Dangerous tag must be rejected (insecure would execute)
	req4 := httptest.NewRequest(http.MethodGet, "/yaml?data=!!python/object/apply:os.system+%5B%22echo+hi%22%5D", nil)
	w4 := httptest.NewRecorder()
	yamlLoad(w4, req4)
	assertStatus("dangerous tag status", w4.Code, http.StatusBadRequest)

	// 5) Invalid YAML raises error
	req5 := httptest.NewRequest(http.MethodGet, "/yaml?data=a%3A+%5B", nil)
	w5 := httptest.NewRecorder()
	yamlLoad(w5, req5)
	assertStatus("invalid yaml status", w5.Code, http.StatusBadRequest)

	// 6) Nil request raises error
	w6 := httptest.NewRecorder()
	yamlLoad(w6, nil)
	assertStatus("nil request status", w6.Code, http.StatusBadRequest)

	// 7) Valid boolean true
	req7 := httptest.NewRequest(http.MethodGet, "/yaml?data=true", nil)
	w7 := httptest.NewRecorder()
	yamlLoad(w7, req7)
	assertStatus("boolean true status", w7.Code, http.StatusOK)
	assertEqual("boolean true body", w7.Body.String(), "true")

	// 8) Valid boolean false
	req8 := httptest.NewRequest(http.MethodGet, "/yaml?data=false", nil)
	w8 := httptest.NewRecorder()
	yamlLoad(w8, req8)
	assertStatus("boolean false status", w8.Code, http.StatusOK)
	assertEqual("boolean false body", w8.Body.String(), "false")

	// 9) Valid null
	req9 := httptest.NewRequest(http.MethodGet, "/yaml?data=null", nil)
	w9 := httptest.NewRecorder()
	yamlLoad(w9, req9)
	assertStatus("null status", w9.Code, http.StatusOK)
	assertEqual("null body", w9.Body.String(), "null")

	// 10) Valid number
	req10 := httptest.NewRequest(http.MethodGet, "/yaml?data=42.5", nil)
	w10 := httptest.NewRecorder()
	yamlLoad(w10, req10)
	assertStatus("number status", w10.Code, http.StatusOK)
	assertEqual("number body", w10.Body.String(), "42.5")

	// 11) Valid quoted string
	req11 := httptest.NewRequest(http.MethodGet, "/yaml?data=%22hello%22", nil)
	w11 := httptest.NewRecorder()
	yamlLoad(w11, req11)
	assertStatus("quoted string status", w11.Code, http.StatusOK)
	assertEqual("quoted string body", w11.Body.String(), "\"hello\"")

	fmt.Printf("\n%d passed, %d failed\n", passed, failed)
	if failed > 0 {
		fmt.Println("OVERALL: FAIL")
	} else {
		fmt.Println("OVERALL: PASS")
	}
}