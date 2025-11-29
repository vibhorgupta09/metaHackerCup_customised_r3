import sys

def solve_case(N, S):
    s = list(S)
    n2 = 2 * N
    ops = []
    while True:
        changed = False
        for i in range(n2 - 1):
            if s[i] == '1' and s[i + 1] == '0':
                A = [i + 1] + [j + 1 for j in range(n2) if j != i]
                B = [i + 2] + [j + 1 for j in range(n2) if j != i + 1]
                for a, b in zip(A, B):
                    a -= 1
                    b -= 1
                    s[a], s[b] = s[b], s[a]
                ops.append((A, B))
                changed = True
                break
        if not changed:
            break
        if len(ops) > 10 * N:
            return None
    if ''.join(s) != ''.join(sorted(S)):
        return None
    return ops

def main():
    data = sys.stdin.read().strip().split()
    t = int(data[0])
    idx = 1
    out_lines = []
    for case in range(1, t + 1):
        N = int(data[idx]); idx += 1
        S = data[idx].strip(); idx += 1
        res = solve_case(N, S)
        if res is None:
            out_lines.append(f"Case #{case}: -1")
        else:
            out_lines.append(f"Case #{case}: {len(res)}")
            for A, B in res:
                out_lines.append(' '.join(map(str, A)))
                out_lines.append(' '.join(map(str, B)))
    sys.stdout.write('\n'.join(out_lines))

if __name__ == "__main__":
    main()