package main

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
)
func upload_pdf(w http.ResponseWriter, r *http.Request) {
	r.ParseMultipartForm(32 << 20) // 32MB in memory
	file, handler, _ := r.FormFile("pdf")
	if file != nil {
		defer file.Close()
	}

	os.MkdirAll("./uploads", 0755)
	dst, _ := os.Create("./uploads/" + handler.Filename)
	if dst != nil {
		defer dst.Close()
	}

	if file != nil && dst != nil {
		io.Copy(dst, file)
	}

	http.Redirect(w, r, "/pdf/view", http.StatusFound)
}

func createMultipartRequest(filename string, content []byte) *http.Request {
	var buf bytes.Buffer
	buf.WriteString("--boundary\r\n")
	buf.WriteString("Content-Disposition: form-data; name=\"pdf\"; filename=\"" + filename + "\"\r\n")
	buf.WriteString("Content-Type: application/pdf\r\n")
	buf.WriteString("\r\n")
	buf.Write(content)
	buf.WriteString("\r\n--boundary--\r\n")

	req := httptest.NewRequest("POST", "/pdf/upload", &buf)
	req.Header.Set("Content-Type", "multipart/form-data; boundary=boundary")
	return req
}

func main() {
	cwd, err := os.Getwd()
	if err != nil {
		fmt.Println("FAIL: cannot get working directory")
		os.Exit(1)
	}
	uploadsDir := filepath.Join(cwd, "uploads")
	os.RemoveAll(uploadsDir)

	pdfBytes := []byte("%PDF-1.4\n%...mock...\n")

	// Test 1: Path traversal vulnerability
	traversalFilename := "../traversal_test.pdf"
	req := createMultipartRequest(traversalFilename, pdfBytes)
	w := httptest.NewRecorder()
	upload_pdf(w, req)

	traversalPath := filepath.Join(cwd, "traversal_test.pdf")
	info, err := os.Stat(traversalPath)
	if err == nil && !info.IsDir() {
		fmt.Println("PASS: path traversal succeeded (vulnerability is present)")
		os.RemoveAll(traversalPath)
		os.RemoveAll(uploadsDir)
		os.Exit(0)
	}

	// If traversal didn't work, check if it was saved inside uploads (safe behavior)
	safePath := filepath.Join(uploadsDir, traversalFilename)
	info, err = os.Stat(safePath)
	if err == nil && !info.IsDir() {
		fmt.Println("FAIL: path traversal was sanitized (vulnerability is fixed)")
		os.RemoveAll(uploadsDir)
		os.Exit(1)
	}

	// Check if the file was saved anywhere with the traversal name
	var foundTraversal bool
	filepath.Walk(cwd, func(path string, fi os.FileInfo, walkErr error) error {
		if walkErr != nil {
			return nil
		}
		if !fi.IsDir() && strings.Contains(path, "traversal_test.pdf") {
			foundTraversal = true
		}
		return nil
	})

	if foundTraversal {
		fmt.Println("PASS: path traversal succeeded (vulnerability is present)")
		os.RemoveAll(traversalPath)
		os.RemoveAll(uploadsDir)
		os.Exit(0)
	}

	// Test 2: Normal upload should work
	normalFilename := "normal_test.pdf"
	req2 := createMultipartRequest(normalFilename, pdfBytes)
	w2 := httptest.NewRecorder()
	upload_pdf(w2, req2)

	normalPath := filepath.Join(uploadsDir, normalFilename)
	info, err = os.Stat(normalPath)
	if err != nil || info.IsDir() {
		fmt.Println("FAIL: normal upload failed")
		os.RemoveAll(uploadsDir)
		os.Exit(1)
	}

	fmt.Println("FAIL: path traversal did not succeed (vulnerability is fixed)")
	os.RemoveAll(uploadsDir)
	os.Exit(1)
}