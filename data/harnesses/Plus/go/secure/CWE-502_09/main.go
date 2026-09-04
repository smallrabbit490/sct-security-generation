package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math"
	"unicode/utf8"
)
// LoadCachedReport decodes a base64-encoded string into a cached report tuple.
func LoadCachedReport(blob string) (string, int64, map[string]float64) {
	decoded, err := base64.StdEncoding.DecodeString(blob)
	if err != nil {
		panic("invalid base64")
	}

	if !utf8.Valid(decoded) {
		panic("invalid decoded text")
	}

	var obj map[string]interface{}
	if err := json.Unmarshal(decoded, &obj); err != nil {
		panic("invalid JSON")
	}

	for _, k := range []string{"report_id", "generated_at", "metrics"} {
		if _, ok := obj[k]; !ok {
			panic("missing required field")
		}
	}

	reportIDVal, ok := obj["report_id"].(string)
	if !ok || reportIDVal == "" {
		panic("invalid report_id")
	}

	generatedAtVal := obj["generated_at"]
	var generatedAt int64
	switch v := generatedAtVal.(type) {
	case float64:
		if v != math.Trunc(v) {
			panic("generated_at must be an int")
		}
		generatedAt = int64(v)
	case json.Number:
		f, err := v.Float64()
		if err != nil || f != math.Trunc(f) {
			panic("generated_at must be an int")
		}
		generatedAt = int64(f)
	default:
		panic(fmt.Sprintf("generated_at must be an int"))
	}
	if generatedAt < 0 {
		panic("generated_at must be non-negative")
	}

	metricsVal := obj["metrics"]
	metricsMap, ok := metricsVal.(map[string]interface{})
	if !ok {
		panic(fmt.Sprintf("metrics must be a dict"))
	}

	metrics := make(map[string]float64, len(metricsMap))
	for mk, mv := range metricsMap {
		if mk == "" {
			panic("invalid metric key")
		}
		var f float64
		switch v := mv.(type) {
		case float64:
			f = v
		case json.Number:
			parsed, err := v.Float64()
			if err != nil {
				panic(fmt.Sprintf("metric values must be numeric"))
			}
			f = parsed
		default:
			panic(fmt.Sprintf("metric values must be numeric"))
		}
		metrics[mk] = f
	}

	return reportIDVal, generatedAt, metrics
}

func assertPanic(f func(), message string) {
	defer func() {
		if r := recover(); r == nil {
			panic(fmt.Sprintf("Expected panic but did not panic: %s", message))
		}
	}()
	f()
}

func assertEqual(a, b interface{}) {
	if a != b {
		panic(fmt.Sprintf("Assertion failed: %v != %v", a, b))
	}
}

func assertMapEqual(a, b map[string]float64) {
	if len(a) != len(b) {
		panic(fmt.Sprintf("Map length mismatch: %v != %v", a, b))
	}
	for k, v := range a {
		if bv, ok := b[k]; !ok || v != bv {
			panic(fmt.Sprintf("Map content mismatch at key %s: %v != %v", k, v, bv))
		}
	}
}

func main() {
	// Test 1: Valid full report
	good := map[string]interface{}{
		"report_id":    "r1",
		"generated_at": float64(1700000000),
		"metrics":      map[string]interface{}{"acc": 0.9, "loss": 1.2},
	}
	goodJSON, _ := json.Marshal(good)
	b64 := base64.StdEncoding.EncodeToString(goodJSON)
	rid, gat, met := LoadCachedReport(b64)
	assertEqual(rid, "r1")
	assertEqual(gat, int64(1700000000))
	assertMapEqual(met, map[string]float64{"acc": 0.9, "loss": 1.2})

	// Test 2: Valid empty metrics
	good2 := map[string]interface{}{
		"report_id":    "x",
		"generated_at": float64(0),
		"metrics":      map[string]interface{}{},
	}
	good2JSON, _ := json.Marshal(good2)
	b64_2 := base64.StdEncoding.EncodeToString(good2JSON)
	rid2, gat2, met2 := LoadCachedReport(b64_2)
	assertEqual(rid2, "x")
	assertEqual(gat2, int64(0))
	assertMapEqual(met2, map[string]float64{})

	// Test 3: Non-JSON after decoding
	badText := base64.StdEncoding.EncodeToString([]byte("not json"))
	assertPanic(func() { LoadCachedReport(badText) }, "non-json after decoding")

	// Test 4: JSON but not an object
	badList := base64.StdEncoding.EncodeToString([]byte("[1,2,3]"))
	assertPanic(func() { LoadCachedReport(badList) }, "json but not an object")

	// Test 5: Missing field
	missing := map[string]interface{}{
		"report_id":    "r2",
		"generated_at": float64(1),
	}
	missingJSON, _ := json.Marshal(missing)
	b64Missing := base64.StdEncoding.EncodeToString(missingJSON)
	assertPanic(func() { LoadCachedReport(b64Missing) }, "missing field")

	// Test 6: Wrong types inside metrics
	badMetrics := map[string]interface{}{
		"report_id":    "r3",
		"generated_at": float64(1),
		"metrics":      map[string]interface{}{"a": "x"},
	}
	badMetricsJSON, _ := json.Marshal(badMetrics)
	b64BadMetrics := base64.StdEncoding.EncodeToString(badMetricsJSON)
	assertPanic(func() { LoadCachedReport(b64BadMetrics) }, "wrong types inside metrics")

	// Test 7: Invalid base64
	assertPanic(func() { LoadCachedReport("<not base64>") }, "invalid base64")

	// Test 8: Wrong input type (Go enforces types at compile time, so we ensure the signature requires string)
	// This test is implicitly handled by the compiler. No runtime test needed.

	fmt.Println("All tests passed!")
}