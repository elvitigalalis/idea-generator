SHELL := /bin/bash

ROOT_DIR := $(CURDIR)
GATEWAY_DIR := services/gateway
RANKING_DIR := plugins/ranking-engine
RANKING_INCLUDE := $(RANKING_DIR)/include
RANKING_SRC := $(RANKING_DIR)/src/rank_cpu.cpp
RANKING_LIB_DIR := $(RANKING_DIR)/lib
RANKING_LIB := $(RANKING_LIB_DIR)/librank_cpu.dylib
MACOS_RPATH := @loader_path/../../../../plugins/ranking-engine/lib
CGO_RUNTIME_LDFLAGS := -Wl,-rpath,$(MACOS_RPATH)
GO_CACHE := $(ROOT_DIR)/.gocache

.PHONY: clean compile test run

compile:
	@mkdir -p $(RANKING_LIB_DIR)
	clang++ -O3 -std=c++17 -shared -fPIC \
		-I$(RANKING_INCLUDE) \
		-install_name @rpath/librank_cpu.dylib \
		-o $(RANKING_LIB) \
		$(RANKING_SRC)

test: compile
	GOCACHE="$(GO_CACHE)" CGO_LDFLAGS="$(CGO_RUNTIME_LDFLAGS)" go test ./...

run: compile
	cd $(GATEWAY_DIR) && GOCACHE="$(GO_CACHE)" CGO_LDFLAGS="$(CGO_RUNTIME_LDFLAGS)" go run .

clean:
	rm -rf $(RANKING_LIB_DIR) $(GO_CACHE)
