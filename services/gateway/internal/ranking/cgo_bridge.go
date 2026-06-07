//go:build darwin

package ranking

/*
#cgo CFLAGS: -I../../../../plugins/ranking-engine/include
#cgo LDFLAGS: -L../../../../plugins/ranking-engine/lib -Wl,-rpath,${SRCDIR}/../../../../plugins/ranking-engine/lib -lrank_cpu
#include "rank.h"
*/
import "C"

import (
	"runtime"
	"unsafe"
)

func RankIdeas(scores []float32) float32 {
	if len(scores) == 0 {
		return 0
	}

	var out float32
	C.run_parallel_reduction(
		(*C.float)(unsafe.Pointer(unsafe.SliceData(scores))),
		(*C.float)(unsafe.Pointer(&out)),
		C.int(len(scores)),
	)
	runtime.KeepAlive(scores)
	return out
}
