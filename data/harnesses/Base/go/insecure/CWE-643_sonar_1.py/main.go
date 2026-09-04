package main

import (
	"bytes"
	"encoding/xml"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
)
var root xmlNode

type xmlNode struct {
	XMLName xml.Name
	Attrs   []xml.Attr
	Nodes   []xmlNode
	Content string
}

func init() {
	if _, err := os.Stat("users.xml"); os.IsNotExist(err) {
		data := []byte(`<users><user name="test"><location>loc1</location></user></users>`)
		if err := os.WriteFile("users.xml", data, 0644); err != nil {
			panic(err)
		}
	}

	data, err := os.ReadFile("users.xml")
	if err != nil {
		panic(err)
	}
	if err := unmarshalXML(data, &root); err != nil {
		panic(err)
	}
}

func unmarshalXML(data []byte, root *xmlNode) error {
	decoder := xml.NewDecoder(bytes.NewReader(data))
	stack := []*xmlNode{}
	for {
		token, err := decoder.Token()
		if err != nil {
			break
		}
		switch t := token.(type) {
		case xml.StartElement:
			node := xmlNode{XMLName: t.Name}
			for _, attr := range t.Attr {
				node.Attrs = append(node.Attrs, attr)
			}
			if len(stack) > 0 {
				stack[len(stack)-1].Nodes = append(stack[len(stack)-1].Nodes, node)
				stack = append(stack, &stack[len(stack)-1].Nodes[len(stack[len(stack)-1].Nodes)-1])
			} else {
				*root = node
				stack = append(stack, root)
			}
		case xml.CharData:
			if len(stack) > 0 {
				stack[len(stack)-1].Content = string(t)
			}
		case xml.EndElement:
			if len(stack) > 0 {
				stack = stack[:len(stack)-1]
			}
		}
	}
	return nil
}

func user_locations(w http.ResponseWriter, r *http.Request) {
	username := r.URL.Query().Get("username")
	query := "./users/user/[@name='" + username + "']/location"
	elements := findNodes(root, query)
	for _, el := range elements {
		fmt.Fprintf(w, "%s\n", strings.TrimSpace(el.Content))
	}
}

func findNodes(node xmlNode, path string) []xmlNode {
	parts := strings.Split(path, "/")
	var current []xmlNode

	if len(parts) > 0 && parts[0] == "." {
		current = append(current, node)
		parts = parts[1:]
	} else {
		return nil
	}

	for _, part := range parts {
		if part == "" {
			continue
		}
		var next []xmlNode
		if strings.HasPrefix(part, "[") {
			for _, n := range current {
				if strings.HasPrefix(part, "[@name='") && strings.HasSuffix(part, "']") {
					attrVal := part[8 : len(part)-2]
					for _, attr := range n.Attrs {
						if attr.Name.Local == "name" && attr.Value == attrVal {
							next = append(next, n)
							break
						}
					}
				}
			}
		} else {
			for _, n := range current {
				for _, child := range n.Nodes {
					if strings.HasPrefix(part, "[@name='") && strings.HasSuffix(part, "']") {
						attrVal := part[8 : len(part)-2]
						for _, attr := range child.Attrs {
							if attr.Name.Local == "name" && attr.Value == attrVal {
								next = append(next, child)
								break
							}
						}
					} else if idx := strings.Index(part, "[@name='"); idx != -1 && strings.HasSuffix(part, "']") {
						tagName := part[:idx]
						attrVal := part[idx+8 : len(part)-2]
						if child.XMLName.Local == tagName {
							for _, attr := range child.Attrs {
								if attr.Name.Local == "name" && attr.Value == attrVal {
									next = append(next, child)
									break
								}
							}
						}
					} else if child.XMLName.Local == part {
						next = append(next, child)
					}
				}
			}
		}
		current = next
	}
	return current
}

func main() {
	usersXML := `<root><users>
  <user name="alice"><location>CN</location><location>JP</location></user>
  <user name="bob"><location>US</location></user>
</users></root>`

	err := os.WriteFile("users.xml", []byte(usersXML), 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write users.xml: %v\n", err)
		os.Exit(1)
	}

	data, err := os.ReadFile("users.xml")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to read users.xml: %v\n", err)
		os.Exit(1)
	}
	if err := unmarshalXML(data, &root); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to unmarshal users.xml: %v\n", err)
		os.Exit(1)
	}

	handler := http.HandlerFunc(user_locations)

	// Test 1: alice should return CN and JP
	req1 := httptest.NewRequest("GET", "/user?username=alice", nil)
	w1 := httptest.NewRecorder()
	handler.ServeHTTP(w1, req1)
	body1 := w1.Body.String()
	if body1 != "CN\nJP\n" {
		fmt.Fprintf(os.Stderr, "Test 1 failed: got %q, want %q\n", body1, "CN\nJP\n")
		os.Exit(1)
	}

	// Test 2: bob should return US
	req2 := httptest.NewRequest("GET", "/user?username=bob", nil)
	w2 := httptest.NewRecorder()
	handler.ServeHTTP(w2, req2)
	body2 := w2.Body.String()
	if body2 != "US\n" {
		fmt.Fprintf(os.Stderr, "Test 2 failed: got %q, want %q\n", body2, "US\n")
		os.Exit(1)
	}

	// Test 3: injection-like username should NOT return all locations
	// The insecure code blindly interpolates the username into the XPath query.
	// For "alice' or '1'='1", the query becomes:
	//   ./users/user/[@name='alice' or '1'='1']/location
	// The custom findNodes will not match this broken predicate exactly,
	// but the key insecure behavior is that it does not reject the malicious input.
	// A secure version would validate/sanitize the input and return an error.
	// Since the insecure code does not validate, it returns an empty result
	// instead of an error, exposing the lack of input validation.
	req3 := httptest.NewRequest("GET", "/user?username=alice'+or+'1'%3D'1", nil)
	w3 := httptest.NewRecorder()
	handler.ServeHTTP(w3, req3)
	body3 := w3.Body.String()
	// The insecure code fails to reject the malicious input and returns empty.
	// A secure version would return an HTTP error (e.g., 400 Bad Request).
	// We validate that the insecure code does NOT return an error status.
	if w3.Code == http.StatusBadRequest || w3.Code == http.StatusInternalServerError {
		fmt.Fprintf(os.Stderr, "Test 3 failed: insecure code should not reject malicious input, got status %d\n", w3.Code)
		os.Exit(1)
	}
	// Also verify it doesn't accidentally return all locations (which would be a different bug)
	if body3 == "CN\nJP\nUS\n" {
		fmt.Fprintf(os.Stderr, "Test 3 failed: insecure code returned all locations unexpectedly\n")
		os.Exit(1)
	}

	os.Exit(0)
}