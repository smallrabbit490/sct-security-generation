package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
)
// The original Python insecure code uses pickle.loads(), which deserializes arbitrary
// Python objects and is vulnerable to CWE-502 (Deserialization of Untrusted Data).
// The insecure Python outcome is that it accepts valid pickle payloads (which happen
// to also be valid JSON in these specific test cases) and returns the deserialized data.
// For invalid/malformed inputs, the insecure Python code raises exceptions (ValueError, TypeError).
//
// The translated Go code uses encoding/json instead of pickle, which is inherently safe
// from arbitrary deserialization. However, to match the insecure behavior's functional
// outcome (accepting the given inputs and raising errors on bad inputs), the Go code
// must successfully parse the valid JSON inputs and panic on invalid inputs.
// If the Go code fails to parse valid inputs or fails to panic on invalid inputs,
// it does not match the expected insecure behavior, and the validation exits non-zero.

func loadCachedReport(blob string) (string, int64, map[string]float64) {
	data, err := base64.StdEncoding.DecodeString(blob)
	if err != nil {
		panic(err)
	}
	var raw struct {
		ReportID    *string                `json:"report_id"`
		GeneratedAt *int64                 `json:"generated_at"`
		Metrics     map[string]interface{} `json:"metrics"`
	}
	err = json.Unmarshal(data, &raw)
	if err != nil {
		panic(err)
	}
	if raw.ReportID == nil || raw.GeneratedAt == nil || raw.Metrics == nil {
		panic("missing field")
	}
	metrics := make(map[string]float64)
	for k, v := range raw.Metrics {
		f, ok := v.(float64)
		if !ok {
			panic("wrong type in metrics")
		}
		metrics[k] = f
	}
	return *raw.ReportID, *raw.GeneratedAt, metrics
}

func assertPanics(fn func()) {
	defer func() {
		if r := recover(); r == nil {
			fmt.Println("FAIL: expected panic but did not panic")
			os.Exit(1)
		}
	}()
	fn()
}

func main() {
	// Test 1: Valid input
	good := `{"report_id": "r1", "generated_at": 1700000000, "metrics": {"acc": 0.9, "loss": 1.2}}`
	b64_1 := base64.StdEncoding.EncodeToString([]byte(good))
	id1, at1, m1 := loadCachedReport(b64_1)
	if id1 != "r1" || at1 != 1700000000 || m1["acc"] != 0.9 || m1["loss"] != 1.2 {
		fmt.Println("FAIL: good input mismatch")
		os.Exit(1)
	}

	// Test 2: Valid input with empty metrics
	good2 := `{"report_id": "x", "generated_at": 0, "metrics": {}}`
	b64_2 := base64.StdEncoding.EncodeToString([]byte(good2))
	id2, at2, m2 := loadCachedReport(b64_2)
	if id2 != "x" || at2 != 0 || len(m2) != 0 {
		fmt.Println("FAIL: good2 input mismatch")
		os.Exit(1)
	}

	// Test 3: Non-JSON after decoding (Python insecure code raises ValueError)
	badText := base64.StdEncoding.EncodeToString([]byte("not json"))
	assertPanics(func() { loadCachedReport(badText) })

	// Test 4: JSON but not an object (Python insecure code raises ValueError)
	badList := base64.StdEncoding.EncodeToString([]byte("[1,2,3]"))
	assertPanics(func() { loadCachedReport(badList) })

	// Test 5: Missing field (Python insecure code raises ValueError/AttributeError)
	missing := base64.StdEncoding.EncodeToString([]byte(`{"report_id": "r2", "generated_at": 1}`))
	assertPanics(func() { loadCachedReport(missing) })

	// Test 6: Wrong types inside metrics (Python insecure code raises TypeError/ValueError)
	badMetrics := base64.StdEncoding.EncodeToString([]byte(`{"report_id": "r3", "generated_at": 1, "metrics": {"a": "x"}}`))
	assertPanics(func() { loadCachedReport(badMetrics) })

	// Test 7: Invalid base64 (Python insecure code raises ValueError)
	assertPanics(func() { loadCachedReport("<not base64>") })

	// All insecure behavior outcomes matched successfully
	os.Exit(0)
}