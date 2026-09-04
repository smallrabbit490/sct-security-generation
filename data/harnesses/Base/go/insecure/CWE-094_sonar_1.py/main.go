package main

import (
	"bytes"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"strings"
)

// index is the translated function under test.
func index(w http.ResponseWriter, r *http.Request) {
	/*
		Get the module version from the request object
		importing the urllib module with the version by using exec()
	*/
	module := r.URL.Query().Get("module")
	cmd := exec.Command("python", "-c", fmt.Sprintf("import urllib%s as urllib", module))
	cmd.Run()
	fmt.Fprint(w, "Module imported")
}

func main() {
	// Check if python is available in the environment.
	if _, err := exec.LookPath("python"); err != nil {
		fmt.Println("SKIP: python interpreter not found")
		os.Exit(0)
	}

	passed := true
	tests := []struct {
		name     string
		module   string
		wantCode int
		wantBody string
	}{
		{
			name:     "empty module",
			module:   "",
			wantCode: 200,
			wantBody: "Module imported",
		},
		{
			name:     "valid module .parse",
			module:   ".parse",
			wantCode: 200,
			wantBody: "Module imported",
		},
		{
			name:     "valid module .request",
			module:   ".request",
			wantCode: 200,
			wantBody: "Module imported",
		},
		{
			name:     "injection attempt",
			module:   ";raise Exception()#",
			wantCode: 200,
			wantBody: "Module imported",
		},
		{
			name:     "None equivalent (empty string in Go)",
			module:   "",
			wantCode: 200,
			wantBody: "Module imported",
		},
	}

	for _, tt := range tests {
		req := httptest.NewRequest("GET", "/?module="+tt.module, nil)
		w := httptest.NewRecorder()

		index(w, req)

		resp := w.Result()
		bodyBuf := new(bytes.Buffer)
		bodyBuf.ReadFrom(resp.Body)
		body := strings.TrimSpace(bodyBuf.String())

		if resp.StatusCode != tt.wantCode || body != tt.wantBody {
			fmt.Printf("FAIL [%s]: got status %d body %q, want status %d body %q\n",
				tt.name, resp.StatusCode, body, tt.wantCode, tt.wantBody)
			passed = false
		}
	}

	if passed {
		fmt.Println("PASS")
		os.Exit(0)
	} else {
		os.Exit(1)
	}
}