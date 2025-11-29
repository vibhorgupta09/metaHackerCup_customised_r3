import sys

def solve_case(N, S):
    s = list(S)
    ops = []
    n2 = 2 * N

    def do_op(A, B):
        ops.append((A[:], B[:]))
        for i in range(N):
            ai = A[i] - 1
            bi = B[i] - 1
            s[ai], s[bi] = s[bi], s[ai]

    while True:
        i = 0
        while i < n2 and s[i] == '0':
            i += 1
        j = n2 - 1
        while j >= 0 and s[j] == '1':
            j -= 1
        if i >= j:
            break
        A = []
        B = []
        for k in range(1, N + 1):
            if k <= i:
                A.append(k)
            else:
                B.append(k)
        for k in range(N + 1, n2 + 1):
            if k <= j + 1:
                B.append(k)
            else:
                A.append(k)
        do_op(A, B)
        if len(ops) > 10 * N:
            return None
    return ops

def main():
    it = iter(sys.stdin.read().strip().split())
    T = int(next(it))
    out_lines = []
    for tc in range(1, T + 1):
        N = int(next(it))
        S = next(it).strip()
        ops = solve_case(N, S)
        if ops is None:
            out_lines.append(f"Case #{tc}: -1")
        else:
            out_lines.append(f"Case #{tc}: {len(ops)}")
            for A, B in ops:
                out_lines.append(" ".join(map(str, A)))
                out_lines.append(" ".join(map(str, B)))
    sys.stdout.write("\n".join(out_lines))

if __name__ == "__main__":
    main()