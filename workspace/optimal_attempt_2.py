import sys

def solve_case(N, S):
    s = list(S)
    ops = []
    def do_op(A, B):
        nonlocal s, ops
        ops.append((A[:], B[:]))
        for i in range(N):
            ai = A[i] - 1
            bi = B[i] - 1
            s[ai], s[bi] = s[bi], s[ai]

    total_len = 2 * N
    zeros = s.count('0')
    ones = total_len - zeros
    if zeros == 0 or ones == 0:
        return []

    for i in range(total_len):
        desired = '0' if i < zeros else '1'
        if s[i] == desired:
            continue
        j = i + 1
        while j < total_len and s[j] == s[i]:
            j += 1
        if j == total_len:
            return None
        A = []
        B = []
        used = [False] * total_len
        A.append(i + 1)
        B.append(j + 1)
        used[i] = used[j] = True
        for k in range(total_len):
            if not used[k]:
                if len(A) < N:
                    A.append(k + 1)
                else:
                    B.append(k + 1)
        do_op(A, B)
        if len(ops) > 10 * N:
            return None

    if ''.join(s) != '0' * zeros + '1' * ones:
        return None
    return ops

def main():
    data = sys.stdin.read().strip().split()
    t = int(data[0])
    out_lines = []
    idx = 1
    for case in range(1, t + 1):
        N = int(data[idx]); idx += 1
        S = data[idx].strip(); idx += 1
        ops = solve_case(N, S)
        if ops is None or len(ops) > 10 * N:
            out_lines.append(f"Case #{case}: -1")
        else:
            out_lines.append(f"Case #{case}: {len(ops)}")
            for A, B in ops:
                out_lines.append(' '.join(map(str, A)))
                out_lines.append(' '.join(map(str, B)))
    sys.stdout.write('\n'.join(out_lines))

if __name__ == "__main__":
    main()