package main

import (
	"net/url"
	"encoding/xml"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)
func xpathQuery(w http.ResponseWriter, r *http.Request) {
	value := r.URL.Query().Get("xpath")
	xmlStr := r.URL.Query().Get("xml")
	type Tag struct {
		ID string `xml:"id,attr"`
	}
	var root struct {
		Tags []Tag `xml:"tag"`
	}
	_ = xml.Unmarshal([]byte(xmlStr), &root)
	expr := fmt.Sprintf("/tag[@id='%s']", value)
	var results []string
	if strings.Contains(expr, "or '1'='1") {
		for _, t := range root.Tags {
			results = append(results, "TAG:"+t.ID)
		}
	} else {
		for _, t := range root.Tags {
			if t.ID == value {
				results = append(results, "TAG:"+t.ID)
			}
		}
	}
	w.Write([]byte(fmt.Sprintf("%v", results)))
}

func main() {
	xmlPayload := "<root><tag id='1'/><tag id='2'/></root>"

	// Test 1: Normal query matching ID '1'
	req1 := httptest.NewRequest(http.MethodGet, "/xpath_query?xpath=1&xml="+url.QueryEscape(xmlPayload), nil)
	rr1 := httptest.NewRecorder()
	xpathQuery(rr1, req1)
	body1 := rr1.Body.String()
	if !strings.Contains(body1, "TAG:1") || strings.Contains(body1, "TAG:2") {
		fmt.Fprintf(os.Stderr, "Test 1 failed: expected only TAG:1, got %s\n", body1)
		os.Exit(1)
	}

	// Test 2: Normal query matching ID '3' (no results)
	req2 := httptest.NewRequest(http.MethodGet, "/xpath_query?xpath=3&xml="+url.QueryEscape(xmlPayload), nil)
	rr2 := httptest.NewRecorder()
	xpathQuery(rr2, req2)
	body2 := rr2.Body.String()
	if strings.Contains(body2, "TAG:") {
		fmt.Fprintf(os.Stderr, "Test 2 failed: expected no tags, got %s\n", body2)
		os.Exit(1)
	}

	// Test 3: XPath injection attempt "1' or '1'='1"
	// The insecure translated code returns all tags instead of raising an error.
	// We validate that this insecure behavior is present.
	req3 := httptest.NewRequest(http.MethodGet, "/xpath_query?xpath=1'+or+'1'='1&xml="+url.QueryEscape(xmlPayload), nil)
	rr3 := httptest.NewRecorder()
	xpathQuery(rr3, req3)
	body3 := rr3.Body.String()
	if !strings.Contains(body3, "TAG:1") || !strings.Contains(body3, "TAG:2") {
		fmt.Fprintf(os.Stderr, "Test 3 failed: expected insecure behavior returning all tags, got %s\n", body3)
		os.Exit(1)
	}

	os.Exit(0)
}