#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
berjalan.py - animasi terminal: seseorang berjalan sendirian di bawah hujan,
tubuhnya tersusun dari potongan kode.

Jalankan  : python berjalan.py
Ulang terus: python berjalan.py --ulang
Tips rekam: perbesar jendela terminal (disarankan 90x32 atau lebih), font gelap,
            lalu rekam layar. Keluar kapan saja dengan Ctrl+C.
Tanpa library tambahan, cukup Python 3.8+.
"""
import math
import os
import random
import re
import shutil
import sys
import time

FPS = 24
DURASI = 34.0          # detik sampai langkah berhenti
TAHAN = 4.0            # detik tahan di akhir
OMEGA = 2 * math.pi / 2.0   # satu siklus langkah = 2 detik (pelan, lesu)
AMP = 0.30                  # ayunan kaki
KECEPATAN = 9.0             # kecepatan tanah bergeser (kolom/detik)

QUOTE = [
    "...................................",
    "...................................",
    "...................................",
    "...................................",
]
MUNCUL = [4.0, 8.5, 13.0, 18.0, 23.5]   # detik tiap baris mulai diketik

KODE = '''
def berjuang(diri):
    risiko = ambil_semua()
    try:
        usaha(diri, sendirian=True)
    except Lelah as e:
        diam(e)   # tidak cerita
    finally:
        doa("ya Tuhan permudahkan lah")
    return langkah + 1
while hidup:
    langkah = lanjut()   # pelan-pelan
    if beban > kuat:
        sabar()
    print("tetap jalan")
'''

KATA_KUNCI = {"def", "try", "except", "finally", "return", "while", "if", "as", "True"}


def siapkan_kode():
    """Ubah teks kode jadi daftar (karakter, warna) berwarna ala editor."""
    hasil = []
    for baris in KODE.strip().splitlines():
        b = baris.strip()
        if not b:
            continue
        for m in re.finditer(r'(#.*)|("[^"]*")|(\d+)|([A-Za-z_]\w*)|(\s)|(.)', b):
            tok = m.group(0)
            if m.group(1):
                col = 60
            elif m.group(2):
                col = 137
            elif m.group(3):
                col = 108
            elif m.group(4):
                col = 104 if tok in KATA_KUNCI else 252
            else:
                col = 245
            for ch in tok:
                hasil.append(("·", 240) if ch.isspace() else (ch, col))
        hasil.append(("·", 240))
        hasil.append(("·", 240))
    return hasil


def titik_ke_segmen(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - ax, py - ay)
    u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + u * dx), py - (ay + u * dy))


def bangun_pose(phase, sf, k, cx, gyu):
    """Kerangka orang (tampak samping) sebagai daftar segmen tebal.
    Satuan: 1 unit = 1 kolom = setengah baris. sf = 0..1 (0 = berdiri diam)."""
    amp = AMP * sf
    bob = abs(math.sin(phase)) * 0.9 * k * sf
    hx, hy = cx, gyu - 18 * k + bob
    segs = []

    for off in (0.0, math.pi):                      # dua kaki
        ph = phase + off
        a = amp * math.sin(ph)
        bend = 0.95 * max(0.0, math.cos(ph)) * sf
        kx, ky = hx + 9 * k * math.sin(a), hy + 9 * k * math.cos(a)
        b = a - bend
        fx, fy = kx + 9 * k * math.sin(b), ky + 9 * k * math.cos(b)
        segs.append((hx, hy, kx, ky, 2.2 * k))
        segs.append((kx, ky, fx, fy, 1.9 * k))
        segs.append((fx, fy, fx + 2.8 * k, fy, 0.9 * k))

    lean = 0.13                                      # badan condong ke depan
    sx, sy = hx + 13 * k * math.sin(lean), hy - 13 * k * math.cos(lean)
    segs.append((hx, hy, sx, sy, 3.1 * k))

    nx, ny = sx + 4.9 * k * math.sin(lean + 0.30), sy - 4.9 * k * math.cos(lean + 0.30)
    segs.append((sx, sy, nx, ny, 1.2 * k))           # leher
    segs.append((nx, ny, nx, ny, 3.4 * k))           # kepala tertunduk

    for off in (0.0, math.pi):                       # dua lengan
        ph = phase + off + math.pi
        a = -0.7 * amp * math.sin(ph) + 0.08
        ex, ey = sx + 6.5 * k * math.sin(a), sy + 6.5 * k * math.cos(a)
        fa = a + 0.25 + 0.35 * max(0.0, math.cos(ph)) * sf
        wx, wy = ex + 6.2 * k * math.sin(fa), ey + 6.2 * k * math.cos(fa)
        segs.append((sx, sy, ex, ey, 1.3 * k))
        segs.append((ex, ey, wx, wy, 1.1 * k))
    return segs


class Adegan:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.gy = H - 8
        self.k = min(1.15, (self.gy - 3) / 19.5)
        self.cx = W * 0.42
        self.phase = 0.0
        self.scroll = 0.0
        self.sf = 1.0
        self.kode = siapkan_kode()
        rnd = random.Random(7)
        self.hujan = [[rnd.uniform(0, W), rnd.uniform(0, self.gy),
                       rnd.uniform(14, 26), rnd.choice((23, 24, 60))]
                      for _ in range(W // 2)]

    def update(self, dt, t):
        sf = 1.0
        if t > DURASI - 6:
            sf = max(0.0, min(1.0, (DURASI - 2 - t) / 4.0))
            sf = sf * sf * (3 - 2 * sf)
        self.sf = sf
        self.phase += OMEGA * sf * dt
        self.scroll += KECEPATAN * sf * dt
        for d in self.hujan:
            d[1] += d[2] * dt
            d[0] -= 4 * dt
            if d[1] >= self.gy:
                d[1] = random.uniform(-6, 0)
                d[0] = random.uniform(0, self.W + 8)

    def gambar(self, t):
        W, H, gy, k = self.W, self.H, self.gy, self.k
        g = [[(" ", None) for _ in range(W)] for _ in range(H)]

        def taruh(r, c, ch, col):
            if 0 <= r < H and 0 <= c < W:
                g[r][c] = (ch, col)

        # hujan
        for x, y, _, col in self.hujan:
            taruh(int(y), int(x), "│", col)

        # lampu jalan (lapisan jauh, bergeser lebih pelan)
        off = (self.scroll * 0.35) % 42
        for n in range(-1, W // 42 + 3):
            lx = int(n * 42 - off)
            for r in range(gy - 10, gy):
                taruh(r, lx, "│", 238)
            taruh(gy - 11, lx, "●", 137)
            for dx in (-2, -1, 1, 2):
                taruh(gy - 11, lx + dx, "·", 94)

        # tanah
        for c in range(W):
            taruh(gy, c, "─", 238)
            if (c + int(self.scroll)) % 9 == 0:
                taruh(gy + 1, c, "·", 237)

        # sosok dari kode
        segs = bangun_pose(self.phase, self.sf, k, self.cx, gy * 2)
        isi = set()
        for r in range(max(0, gy - 28), gy + 1):
            py = (r + 0.5) * 2
            for c in range(int(self.cx - 22), int(self.cx + 23)):
                px = c + 0.5
                for ax, ay, bx, by, rad in segs:
                    if titik_ke_segmen(px, py, ax, ay, bx, by) <= rad:
                        isi.add((r, c))
                        break
        N = len(self.kode)
        geser = int(t * 5)
        for r, c in isi:
            ch, col = self.kode[(c + r * 31 + geser) % N]
            tepi = any(n not in isi for n in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)))
            if tepi:
                col = 255 if ch != "·" else 245
            taruh(r, c, ch, col)

        # teks bawah
        r0 = gy + 3
        for i, baris in enumerate(QUOTE):
            n = int((t - MUNCUL[i]) * 30)
            if n <= 0:
                continue
            n = min(n, len(baris))
            c0 = (W - len(baris)) // 2
            for j in range(n):
                taruh(r0 + i, c0 + j, baris[j], 252)
            sedang_ketik = n < len(baris)
            terakhir = i == len(QUOTE) - 1 and not sedang_ketik
            if sedang_ketik or (terakhir and int(t * 2) % 2 == 0):
                taruh(r0 + i, c0 + n, "█", 255)

        # status di baris atas
        kiri = "$ python berjalan.py"
        kanan = "langkah = %d" % int(self.phase / math.pi)
        for j, ch in enumerate(kiri):
            taruh(0, 1 + j, ch, 240)
        for j, ch in enumerate(kanan):
            taruh(0, W - len(kanan) - 1 + j, ch, 240)
        return g


def render(g):
    keluar = []
    for baris in g:
        potong, cur = [], "?"
        for ch, col in baris:
            if col != cur:
                potong.append("\033[38;5;%dm" % col if col is not None else "\033[0m")
                cur = col
            potong.append(ch)
        keluar.append("".join(potong))
    return "\033[H" + "\033[0m\n".join(keluar) + "\033[0m"


def ketik(teks, jeda=0.05, warna=None):
    if warna:
        sys.stdout.write("\033[38;5;%dm" % warna)
    for ch in teks:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(jeda)
    sys.stdout.write("\033[0m")


def intro():
    sys.stdout.write("\033[2J\033[H")
    ketik("$ ", 0.0, 108)
    ketik("python berjalan.py", 0.07, 252)
    sys.stdout.write("\n\n")
    for tag, warna, pesan in (
        ("[ ok ]", 108, "memuat semua risiko"),
        ("[ ok ]", 108, "menyiapkan hujan"),
        ("[warn]", 179, "beban > kuat"),
        ("[ .. ]", 245, "memulai langkah, sendirian"),
    ):
        sys.stdout.write("\033[38;5;%dm%s\033[0m %s\n" % (warna, tag, pesan))
        sys.stdout.flush()
        time.sleep(0.6)
    time.sleep(0.8)
    sys.stdout.write("\033[2J\033[H")


def putar(W, H):
    sc = Adegan(W, H)
    t0 = sebelum = time.perf_counter()
    while True:
        now = time.perf_counter()
        t = now - t0
        if t > DURASI + TAHAN:
            break
        sc.update(min(now - sebelum, 0.1), t)
        sebelum = now
        sys.stdout.write(render(sc.gambar(t)))
        sys.stdout.flush()
        sisa = 1.0 / FPS - (time.perf_counter() - now)
        if sisa > 0:
            time.sleep(sisa)


def main():
    os.system("")  # mengaktifkan kode warna ANSI di Windows
    kolom, baris = shutil.get_terminal_size((90, 32))
    W = max(60, min(kolom - 1, 110))
    H = max(20, min(baris - 1, 36))
    ulang = "--ulang" in sys.argv
    try:
        sys.stdout.write("\033[?1049h\033[?25l")
        intro()
        while True:
            putar(W, H)
            if not ulang:
                break
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[0m\033[?25h\033[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    main()