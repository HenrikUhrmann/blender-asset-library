"""Optische Berechnungen: n,k-Daten -> Fresnel-Farben, RGB-Werte, Dünnfilm-Dicken.

Spektral gerechnet (380 bis 780 nm, 5 nm), Umrechnung nach linearem sRGB mit den Farbanpassungsfunktionen von
Wyman, Sloan & Shirley (2013, JCGT 2(2), Mehrfach-Gauß-Näherung der CIE-1931-Funktionen), Beleuchtung gleich-
energetisch (Illuminant E), anschließend weißnormiert: ein perfekter Reflektor (R = 1) ergibt (1, 1, 1).
"""
import glob
import math
import os

import numpy as np
import yaml

HERE = os.path.dirname(__file__)
WL = np.arange(380.0, 780.01, 5.0)  # nm


# ---------------------------------------------------------------- Daten laden
def load_nk(key):
    """Gibt (lambda_nm[], n[], k[]) für eine Datei aus data/ zurück (tabulated nk)."""
    d = yaml.safe_load(open(os.path.join(HERE, "data", key + ".yml"), encoding="utf-8"))
    block = d["DATA"][0]
    if block["type"] != "tabulated nk":
        raise ValueError(f"{key}: Typ {block['type']} nicht unterstützt")
    rows = np.array([[float(x) for x in line.split()] for line in block["data"].strip().splitlines()])
    return rows[:, 0] * 1000.0, rows[:, 1], rows[:, 2]


def interp_nk(key, wl=WL):
    lam, n, k = load_nk(key)
    if lam.min() > 400 or lam.max() < 700:
        raise ValueError(f"{key}: Daten decken 400 bis 700 nm nicht ab ({lam.min():.0f} bis {lam.max():.0f} nm)")
    return np.interp(wl, lam, n), np.interp(wl, lam, k)


def reference(key):
    d = yaml.safe_load(open(os.path.join(HERE, "data", key + ".yml"), encoding="utf-8"))
    return " ".join(str(d.get("REFERENCES", "")).split())


# ---------------------------------------------------------------- Farbe
def _g(x, mu, s1, s2):
    return np.exp(-0.5 * ((x - mu) / np.where(x < mu, s1, s2)) ** 2)


def cmf(wl):
    x = 1.056 * _g(wl, 599.8, 37.9, 31.0) + 0.362 * _g(wl, 442.0, 16.0, 26.7) - 0.065 * _g(wl, 501.1, 20.4, 26.2)
    y = 0.821 * _g(wl, 568.8, 46.9, 40.5) + 0.286 * _g(wl, 530.9, 16.3, 31.1)
    z = 1.217 * _g(wl, 437.0, 11.8, 36.0) + 0.681 * _g(wl, 459.0, 26.0, 13.8)
    return np.stack([x, y, z])


XYZ_TO_SRGB = np.array([[3.2404542, -1.5371385, -0.4985314],
                        [-0.9692660, 1.8760108, 0.0415560],
                        [0.0556434, -0.2040259, 1.0572252]])
_CMF = cmf(WL)
_RGB_W = XYZ_TO_SRGB @ _CMF  # 3 x N, Gewichtsfunktionen je Kanal (mit negativen Anteilen)
_WHITE = _RGB_W.sum(axis=1)


def spectrum_to_rgb(refl):
    """Reflexionsspektrum (auf WL) -> lineares sRGB, weißnormiert (R = 1 überall gibt (1, 1, 1))."""
    rgb = (_RGB_W * refl).sum(axis=1) / _WHITE
    return np.clip(rgb, 0.0, 1.0)


def channel_average(values):
    """Kanalgewichteter Mittelwert (z. B. für n und k): nur positive Anteile der sRGB-Gewichtsfunktionen."""
    w = np.clip(_RGB_W, 0.0, None)
    return (w * values).sum(axis=1) / w.sum(axis=1)


# ---------------------------------------------------------------- Fresnel
def fresnel_conductor(n, k, cos_i):
    """Unpolarisierte Reflektanz eines Leiters (Luft -> n + ik) bei Einfallswinkel-Kosinus cos_i."""
    with np.errstate(all='ignore'):
        return _fresnel(n, k, cos_i)


def _fresnel(n, k, cos_i):
    N = n + 1j * k
    sin2 = 1.0 - cos_i ** 2
    root = np.sqrt(N ** 2 - sin2)
    rs = (cos_i - root) / (cos_i + root)
    rp = (N ** 2 * cos_i - root) / (N ** 2 * cos_i + root)
    return 0.5 * (np.abs(rs) ** 2 + np.abs(rp) ** 2)


F82_COS = 1.0 / 7.0  # Blenders F82-Tint-Modell: cos(theta) = 1/7, das sind ca. 81,8 Grad ("82 Grad")


def schlick(f0_rgb, cos_i):
    return f0_rgb + (1.0 - f0_rgb) * (1.0 - cos_i) ** 5


def metal_colors(n, k):
    """(Base Color = F0, Edge Tint, n als RGB, k als RGB) für Spektren n(λ), k(λ).

    Edge Tint nach Blenders Definition (Cycles bsdf_util.h, fresnel_f82tint_B): Wert des echten Fresnel bei
    cos = 1/7 geteilt durch den Schlick-Wert an derselben Stelle (mit F0), je Farbkanal, auf max. 1 begrenzt."""
    f0 = spectrum_to_rgb(fresnel_conductor(n, k, 1.0))
    f82 = spectrum_to_rgb(fresnel_conductor(n, k, F82_COS))
    tint = np.clip(f82 / schlick(f0, F82_COS), 0.0, 1.0)
    f82_rgb = tint * schlick(f0, F82_COS)
    n_rgb, k_rgb = fit_nk(f0, f82_rgb, channel_average(n), channel_average(k))
    return f0, tint, n_rgb, k_rgb


def fit_nk(f0, f82, n_start=None, k_start=None):
    """Je Kanal (n, k) so bestimmen, dass der Leiter-Fresnel F0 (0 Grad) und F82 (cos = 1/7) trifft.
    Damit sind Base Color / Edge Tint (F82-Modus) und IOR / Extinction (Physical Conductor) konsistent.
    Zoomendes Gittersuchverfahren (kein SciPy nötig), n und k in [0, 30]."""
    n_out, k_out = np.zeros(3), np.zeros(3)
    for c in range(3):
        n_lo, n_hi, k_lo, k_hi = 0.0, 30.0, 0.0, 30.0
        for _ in range(8):
            ns = np.linspace(n_lo, n_hi, 121)[:, None]
            ks = np.linspace(k_lo, k_hi, 121)[None, :]
            err = ((fresnel_conductor(ns, ks, 1.0) - f0[c]) ** 2
                   + (fresnel_conductor(ns, ks, F82_COS) - f82[c]) ** 2)
            err = np.nan_to_num(err, nan=1e9)
            i, j = np.unravel_index(np.argmin(err), err.shape)
            n_best, k_best = float(ns[i, 0]), float(ks[0, j])
            dn, dk = (n_hi - n_lo) / 120.0 * 2, (k_hi - k_lo) / 120.0 * 2
            n_lo, n_hi = max(0.0, n_best - dn), n_best + dn
            k_lo, k_hi = max(0.0, k_best - dk), k_best + dk
        n_out[c], k_out[c] = n_best, k_best
    return n_out, k_out


# ---------------------------------------------------------------- Dünnfilm (Normale Inzidenz, Luft / Film / Metall)
def film_reflectance(n_metal, k_metal, n_film, d_nm, wl=WL):
    N2 = n_metal + 1j * k_metal
    r01 = (1.0 - n_film) / (1.0 + n_film)
    r12 = (n_film - N2) / (n_film + N2)
    delta = 2.0 * np.pi * n_film * d_nm / wl
    r = (r01 + r12 * np.exp(2j * delta)) / (1.0 + r01 * r12 * np.exp(2j * delta))
    return np.abs(r) ** 2


def thickness_for_minimum(n_metal, k_metal, n_film, target_nm, d_max=200.0):
    """Kleinste Dicke (nm) > 5, bei der die Reflexion bei target_nm ein lokales Minimum hat (Auslöschung)."""
    ds = np.arange(5.0, d_max, 0.1)
    idx = int(np.argmin(np.abs(WL - target_nm)))
    r = np.array([film_reflectance(n_metal[idx:idx + 1], k_metal[idx:idx + 1], n_film, d, WL[idx:idx + 1])[0]
                  for d in ds])
    for i in range(1, len(ds) - 1):
        if r[i] < r[i - 1] and r[i] <= r[i + 1]:
            return float(ds[i])
    return None
