#!/usr/bin/env python3
"""
Disciples: Sacred Lands – FD portré dekóder & enkóder (önálló, numpy nélkül)
Követelmény: pip install pillow
             + IMGGRAB.BIN (a Disciples telepítőkönyvtárából)

Használat:
  # Összes portré kimentése PNG-be:
  python fd_portrait_codec_standalone.py decode UNIT.DBI kep_mappa/ IMGGRAB.BIN

  # ÚJ portré beillesztése UNIT.DBI-ba (alapértelmezett, modding szempontból
  # ajánlott művelet - nem ír felül semmit, automatikus GP### névgenerálással):
  python fd_portrait_codec_standalone.py encode sajat.png UNIT.DBI IMGGRAB.BIN
  # Kikényszerített prefix+index (pl. natív-stílusú teszthez):
  python fd_portrait_codec_standalone.py encode sajat.png UNIT.DBI IMGGRAB.BIN FN150

  # MEGLÉVŐ portré-slot lecserélése (a régi 'encode' viselkedés - egy adott,
  # név szerint megadott slotot ír felül, méretkorlát nélkül):
  python fd_portrait_codec_standalone.py replace sajat.png UNIT.DBI FD026S00 IMGGRAB.BIN

  # Portré lista:
  python fd_portrait_codec_standalone.py list UNIT.DBI IMGGRAB.BIN
"""

import struct, sys, os, re
from pathlib import Path

# ─── Huffman táblák (azonos minden DBI képhez) ────────────────────────────────

DIST_TABLE = [(0,0),(0,1),(1,2),(2,4),(3,8),(4,16),(5,32),(6,64)]
LEN_TABLE  = [(1,8),(2,10),(3,14),(4,22),(5,38),(6,70),(7,134),(8,262)]

def load_init_codes(imggrab_path):
    """Huffman kódok beolvasása IMGGRAB.BIN-ből."""
    with open(imggrab_path,'rb') as f: igb=f.read()
    ic_raw=0x118A18
    codes={}
    for pos in range(274):
        l=struct.unpack_from('<H',igb,ic_raw+pos*4)[0]
        v=struct.unpack_from('<H',igb,ic_raw+pos*4+2)[0]
        if 1<=l<=16: codes[pos]=(l,v)
    return codes

# ─── Bit I/O ──────────────────────────────────────────────────────────────────

class BitReader:
    def __init__(self,data): self.data=data; self.pos=0
    def read_bit(self):
        b=self.pos>>3; bit=7-(self.pos&7)
        if b>=len(self.data): raise EOFError()
        v=(self.data[b]>>bit)&1; self.pos+=1; return v
    def read_bits(self,n):
        v=0
        for _ in range(n): v=(v<<1)|self.read_bit()
        return v

class BitWriter:
    def __init__(self): self.bits=[]
    def write_bits(self,v,n):
        for i in range(n-1,-1,-1): self.bits.append((v>>i)&1)
    def to_bytes(self):
        while len(self.bits)%8: self.bits.append(0)
        out=bytearray()
        for i in range(0,len(self.bits),8):
            b=0
            for bit in self.bits[i:i+8]: b=(b<<1)|bit
            out.append(b)
        return bytes(out)

# ─── Dekompresszor ────────────────────────────────────────────────────────────

def decompress(stream, init_codes, hp_target):
    """LZ77+Huffman dekompresszió hp_target bájtnyit.

    Az L00 (115x67) portréknál a kompresszor 4096 dekódolt szimbólum
    után egy Huffman-tábla "rebuild" eseményt küld (szimbólum=272).
    Ez az executable (Disciple.exe) reverse engineeringjével felfedezett
    algoritmus szerint zajlik:
      1. A 274 elemű freq[] tömb minden elemét megfelezzük (előjeles
         jobb-shift, "sar"), és a RÉGI (felezés előtti) értékek alapján
         Shell-sorttal növekvő sorrendbe rendezzük a szimbólumokat.
      2. A bitstreamből beolvasunk egy 16-szintű táblát: minden szinten
         unáris kódolással (annyi 0-bit, ahányat jelez, lezárva 1-bittel)
         egy "extra bitek száma" (esi) értéket, ami kumulatív (minden
         szint hozzáadja a saját unáris értékét az előzőhöz). A "base
         index" (honnan kezdődik ez a szint a szimbólumtáblában) az
         előző szintek 2**esi összegéből adódik.
      3. Az új kódtáblával: 4 bit határozza meg a "szintet" (edi), majd
         ha az adott szinthez tartozó esi>0, még esi extra bitet olvas,
         és az eredmény (base_idx[edi]+extra) indexeli a CSÖKKENŐ
         gyakoriság szerint rendezett szimbólumtáblát (a leggyakoribb
         szimbólum az index=0-n).
    """
    # Lookup: kód-string → szimbólum
    lookup={}; max_len=0
    for sym,(l,v) in init_codes.items():
        code=format(v,f'0{l}b')
        lookup[code]=sym
        if l>max_len: max_len=l

    br=BitReader(stream)
    hist=bytearray(max(65536, hp_target+1000))
    hp=0
    freq=[0]*274

    use_new_table=False
    esi_table=None; base_idx_table=None; sym_table=None

    def decode_sym():
        if not use_new_table:
            code=''
            for _ in range(max_len):
                code+=str(br.read_bit())
                if code in lookup: return lookup[code]
            raise ValueError(f"Ismeretlen kód: {code!r}")
        else:
            edi=br.read_bits(4)
            esi=esi_table[edi]
            if esi==0:
                idx=base_idx_table[edi]
            else:
                extra=br.read_bits(esi)
                idx=base_idx_table[edi]+extra
            if idx>=len(sym_table):
                raise ValueError("rebuild index túl nagy")
            return sym_table[idx]

    def read_dist():
        pref=br.read_bits(3); eb,base=DIST_TABLE[pref]
        return (base<<9)|br.read_bits(9+eb)

    def do_rebuild():
        nonlocal use_new_table, esi_table, base_idx_table, sym_table
        pairs=[]
        for i in range(274):
            old=freq[i]
            old_signed = old-65536 if old>=32768 else old
            pairs.append((old, i))
            freq[i] = (old_signed >> 1) & 0xFFFF
        pairs.sort(key=lambda p: p[0])
        sorted_syms=[p[1] for p in pairs]
        sym_table=list(reversed(sorted_syms))
        et=[]; bit=[]; ebp=0; esp10=0
        for _level in range(16):
            cnt=0
            while True:
                b=br.read_bit()
                if b==0: cnt+=1
                else: break
            ebp+=cnt
            et.append(ebp); bit.append(esp10)
            esp10+=(1<<ebp)
        esi_table=et; base_idx_table=bit
        use_new_table=True

    while hp<hp_target:
        try: s=decode_sym()
        except: break

        freq[s]=min(freq[s]+1,0xFFFF)

        if s==272:
            try: do_rebuild()
            except Exception: break
            continue

        if s<256:
            hist[hp]=s; hp+=1
        elif s<264:
            d=read_dist(); l=(s-256)+4; st=hp-d
            for _ in range(l): hist[hp]=hist[st]; hp+=1; st+=1
        elif s<272:
            k=s-264; eb2,base2=LEN_TABLE[k]
            ex=br.read_bits(eb2); l=base2+ex+4
            d=read_dist(); st=hp-d
            for _ in range(l): hist[hp]=hist[st]; hp+=1; st+=1
        elif s==273:
            if hp < hp_target:
                use_new_table = False
                freq = [0]*274
                continue
            break

    return hist, hp



# ─── Kompresszor ──────────────────────────────────────────────────────────────

def compress(data, init_codes):
    """LZ77+Huffman tömörítés (statikus Huffman, S portré).
    
    Optimalizált: minden pozícióban a legjobb (leghosszabb/legolcsóbb) match-et
    keresi a hash-tábla alapján, 256 visszatekintő pozícióval."""
    enc={sym:(l,v) for sym,(l,v) in init_codes.items()}

    bw=BitWriter()
    n=len(data)

    max_eb,max_base=DIST_TABLE[-1]
    MAX_D=(max_base<<9)+((1<<(9+max_eb))-1)

    # Szimbólum bithossza gyors kikereséshez
    sym_bits={sym:l for sym,(l,v) in init_codes.items()}

    def sym(s):
        l,v=enc[s]; bw.write_bits(v,l)

    def dist_bits(d):
        """Hány bitet igényel a távolság kódolása."""
        dh=d>>9; bp,be,bb=0,0,0
        for pf,(eb,base) in enumerate(DIST_TABLE):
            if base<=dh: bp,be,bb=pf,eb,base
        return 3+(9+be)

    def put_dist(d):
        dh=d>>9; bp,be,bb=0,0,0
        for pf,(eb,base) in enumerate(DIST_TABLE):
            if base<=dh: bp,be,bb=pf,eb,base
        bw.write_bits(bp,3); bw.write_bits(d-(bb<<9),9+be)

    def backref_bits(l,d):
        """Hány bitet igényel egy (l,d) visszareferencia."""
        db=dist_bits(d)
        if 4<=l<=11:
            return sym_bits[256+(l-4)]+db
        for k,(eb,base) in enumerate(LEN_TABLE):
            if base+4<=l<=base+(1<<eb)-1+4:
                return sym_bits[264+k]+eb+db
        return 999999

    def put_backref(l,d):
        if 4<=l<=11:
            s2=256+(l-4)
            sym(s2); put_dist(d); return True
        for k,(eb,base) in enumerate(LEN_TABLE):
            if base+4<=l<=base+(1<<eb)-1+4:
                sym(264+k); bw.write_bits(l-base-4,eb); put_dist(d); return True
        return False

    from collections import defaultdict
    ht=defaultdict(list)
    pos=0
    while pos<n:
        # Hash-tábla frissítése a jelenlegi pozícióra
        if pos+2<n:
            key=(data[pos],data[pos+1],data[pos+2])
            ht[key].append(pos)

        bl=0; bd=0; best_bits=sym_bits.get(data[pos],8)+1  # literal cost

        if pos+3<=n:
            key=(data[pos],data[pos+1],data[pos+2])
            candidates=ht.get(key,[])
            # Utolsó 256 jelöltet vizsgálunk (jobb tömörítés)
            for c in reversed(candidates[-256:]):
                d=pos-c
                if d<=0 or d>MAX_D: continue
                ml=min(266,n-pos); l=0
                while l<ml and data[c+l]==data[pos+l]: l+=1
                if l>=4:
                    cost=backref_bits(l,d)
                    # Nyerünk-e a literálishoz képest?
                    lit_cost=sum(sym_bits.get(data[pos+i],8) for i in range(l))
                    if cost<lit_cost and l>bl:
                        bl=l; bd=d; best_bits=cost

        if bl>=4 and put_backref(bl,bd):
            # Hash tábla frissítése az átlépett pozíciókra
            for j in range(1,bl):
                if pos+j+2<n:
                    ht[(data[pos+j],data[pos+j+1],data[pos+j+2])].append(pos+j)
            pos+=bl
        else:
            sym(data[pos]); pos+=1

    sym(273)  # END
    return bw.to_bytes()

# ─── DBI struktúra ────────────────────────────────────────────────────────────

def _search_marker(hist, W, hp, lo, hi, target_ctr, closest_to=None):
    """Egy [K,p1,p2,p3] jelző keresése a [lo,hi) tartományban, p1==target_ctr
    feltétellel és (K<W esetén) az offset-formula érvényesség-ellenőrzésével.
    Ha closest_to meg van adva, a hozzá legközelebbi találatot adja vissza
    (az első jelző kereséséhez); egyébként az ELSŐ találatot (egy adott sor
    TOVÁBBI foltjainak kereséséhez, ahol a sorrend számít).
    """
    best = None
    for cand in range(lo, hi):
        if cand + 3 >= hp:
            break
        K = hist[cand]
        p1 = hist[cand+1]
        if K <= W and p1 == target_ctr:
            if K < W:
                p2c = hist[cand+2]; p3c = hist[cand+3]
                off_c = p3c*8 + (p2c // 32)
                if not (0 <= off_c <= W-K):
                    continue
            if closest_to is not None:
                if best is None or abs(cand - closest_to) < abs(best - closest_to):
                    best = cand
            else:
                return cand
    return best


def _rebuild_rows_v2(hist, W, H, hp):
    """
    ÚJ, validált sor-rekonstrukció (2026-06-18, 5. munkamenet, frissítve a
    "több folt soronként" áttöréssel):
    Minden sor előtt egy [K, p1, p2, p3] 4-bájtos jelző áll (néha 235
    prefixszel, néha anélkül), ahol p1=(4*sor_index) mod 256. Ha K==W, a
    jelzőt követő K bájt a TELJES sor. Ha K<W, a jelzőt követő K bájt a sor
    egy RÉSZE, melynek kezdő oszlopa: offset = p3*8 + p2//32.

    KRITIKUS FELFEDEZÉS: egy sornak TÖBB ilyen [K,p1,p2,p3] foltja is lehet,
    UGYANAZZAL a p1 értékkel, egymás után (validálva: FN127S00 sor37, két
    folt: [0,17) és [36,55), mindkettő bájtra pontosan egyezik az igazsággal).

    A jelzők által NEM lefedett oszlopok az ELŐZŐ (már rekonstruált) sor
    ugyanazon oszlopaiból öröklődnek (közelítés a maradék esetekre).
    """
    rows, _counts = _rebuild_rows_v2_with_counts(hist, W, H, hp)
    return rows


def _rebuild_rows_v2_with_counts(hist, W, H, hp):
    """Mint _rebuild_rows_v2, de minden sorhoz visszaadja a megtalált
    foltok számát is (0 = nincs jelző/fekete sor, 1 = egy folt vagy teljes
    sor, 2+ = több folt - ezekben az esetekben a rekonstrukció bájtra
    pontos, validált explicit adaton alapul, NEM közelítés)."""
    rows, _patches = _rebuild_rows_v2_with_patches(hist, W, H, hp)
    counts = [len(p) for p in _patches]
    return rows, counts


def _rebuild_rows_v2_with_patches(hist, W, H, hp):
    """Mint _rebuild_rows_v2, de minden sorhoz visszaadja a megtalált
    explicit foltok listáját is, (offset,K,explicit_bytes) alakban
    (FULL sor esetén egyetlen (0,W,explicit_bytes) elem). Ez lehetővé
    teszi a foltok PONTOS, oszlop-szintű felülírását egy másik (pl. a
    régi heurisztika) sor-rekonstrukcióján, akkor is, ha csak EGY folt
    található - mivel minden megtalált folt bájtra pontos, validált
    explicit adat, sosem közelítés."""
    rows = []
    all_patches = []
    pos = 0
    for r in range(H):
        target_ctr = (4 * r) % 256
        best = _search_marker(hist, W, hp, max(0, pos-5), min(hp-5, pos+30),
                               target_ctr, closest_to=pos)
        if best is None:
            best = _search_marker(hist, W, hp, max(0, pos-5), min(hp-5, pos+600),
                                   target_ctr, closest_to=pos)
        if best is None:
            rows.append([0]*W)
            all_patches.append([])
            pos += W
            continue

        base = rows[r-1][:] if r > 0 else [0]*W
        row = base[:]
        cur = best
        cur_end = pos
        row_patches = []
        while cur is not None:
            K = hist[cur]
            if K >= W:
                explicit = list(hist[cur+4:cur+4+K])[:W]
                if len(explicit) < W:
                    explicit = explicit + [0]*(W-len(explicit))
                row = explicit
                row_patches.append((0, W, explicit))
                cur_end = cur + 4 + K
                cur = None
                break
            else:
                p2 = hist[cur+2]; p3 = hist[cur+3]
                offset = p3*8 + (p2 // 32)
                offset = max(0, min(offset, W-K))
                explicit = list(hist[cur+4:cur+4+K])
                row[offset:offset+K] = explicit
                row_patches.append((offset, K, explicit))
                cur_end = cur + 4 + K
                cur = _search_marker(hist, W, hp, cur_end, min(hp-5, cur_end+10),
                                      target_ctr)
        rows.append(row[:W])
        all_patches.append(row_patches)
        pos = cur_end
    return rows, all_patches



def _collect_row_markers(hist, W, H, hp_end):

    """
    Sorhatár-markerek ([235, K, counter_lo, counter_hi?, ...]) összegyűjtése.
    A counter mező lehet 1 bájtos VAGY 2 bájtos (LE) - ez a 64+ sorszámú
    portréknál szükséges a 8-bites túlcsordulás miatt, ahol a 2-bájtos
    forma ÜTKÖZHET egy alacsonyabb sorszám 1-bájtos counterjével.
    Az ütközés feloldása: pozíció-konzisztencia (a marker bufferbeli
    pozíciójából becsült sorindexhez közelebbi interpretációt választjuk).
    """
    candidates = []
    for i in range(4, min(hp_end, len(hist)) - 4):
        if hist[i] == 235 and hist[i+1] <= W:
            K_val = hist[i+1]
            est_r = i / (W + 5)
            c1 = hist[i+2]
            r1 = c1 // 4 - 1 if c1 > 0 and c1 % 4 == 0 else None
            c2 = hist[i+2] | (hist[i+3] << 8)
            r2 = c2 // 4 - 1 if c2 > 0 and c2 % 4 == 0 else None
            opts = []
            if r1 is not None and 0 <= r1 < H: opts.append(r1)
            if r2 is not None and 0 <= r2 < H and r2 != r1: opts.append(r2)
            if not opts: continue
            best_r = min(opts, key=lambda r: abs(r - est_r))
            candidates.append((i, K_val, best_r))

    markers_by_row = {}
    for pos, K, r in candidates:
        if r not in markers_by_row:
            markers_by_row[r] = (pos, K)
        else:
            old_pos, _old_K = markers_by_row[r]
            est_pos = r * (W + 5)
            if abs(pos - est_pos) < abs(old_pos - est_pos):
                markers_by_row[r] = (pos, K)
    return markers_by_row


def _find_short_row_pad(hist, pos, ec_full, W, hp_end):
    """
    A rövid sor utáni pad megkeresése (visszaadja a tényleges pixelszámot).
    Két fázisú keresés:
      1. Szigorú minta: [K2<=W, counter_lo, counter_hi, 0] pontos egyezés.
      2. Megengedő minta (csak ha az 1. nem talál): [K2<=W, counter_lo]
         egyezés, counter_hi/maradék bájtok figyelmen kívül hagyva.
    Ha a megtalált jelsorozat egy Típus C placeholder [A,X,B,4] mintájára
    illik (B a 32 többszöröse, a 4. bájt 4), az nem valódi sorhatár-
    marker, hanem egy placeholder, amely a SOR VÉGÉIG ér (suffix nélkül) -
    ilyenkor a visszaadott végpozíció (newpos) a placeholder UTÁNI
    pozícióra mutat, és a hívónak ezt a KÖVETKEZŐ sor (nem rövid) teljes
    adataként kell kezelnie, a marker keresését eltolva (BMP-vel
    validálva: FN127S00 sor35-45 lánc). Ezt a `is_tail_placeholder` jelző
    különbözteti meg.
    """
    ec_lo = ec_full & 0xFF
    ec_hi = (ec_full >> 8) & 0xFF

    for k_test in range(0, W + 1):
        ti = pos + k_test
        if (ti + 3 < hp_end and hist[ti] <= W and
                hist[ti+1] == ec_lo and hist[ti+2] == ec_hi and hist[ti+3] == 0):
            return k_test, hist[ti], ti + 4, False

    for k_test in range(0, W + 1):
        ti = pos + k_test
        if ti + 3 < hp_end and hist[ti] <= W and hist[ti+1] == ec_lo:
            if hist[ti+2] in (32, 64, 96, 128, 160, 192) and hist[ti+3] == 4:
                return k_test, hist[ti], ti + 4, True
            return k_test, hist[ti], ti + 4, False

    return None


# A "placeholder" jelsorozat: a kompresszor ezzel jelzi, hogy egy hosszú
# homogén/átmeneti képrészletet "kihagyott" a rövid sor pixeladatából.
# Formátuma: [P0, P1, P2, P3, X, P5, P6] (7 bájt), ahol X = 4 * (aktuális
# sor index), a [P0,P1,P2,P3] pedig egy ismert "típus-prefixre" illeszkedik
# (eddig megfigyelt típusok: (41,247,191,22) és (23,1,0,18)). A jelsorozat
# előtti és utáni rész valódi pixeladat; a kettő közötti hiányzó szélességet
# egy közeli háttérszínnel (240) töltjük ki.
_PLACEHOLDER_PREFIXES = (
    (41, 247, 191, 22),
    (23, 1, 0, 18),
)


def _reconstruct_short_row(raw_px, row_index, W, prev_row=None):
    """
    Egy kinyert rövid sor pixeladatának (raw_px, hossza k_test) véglegesítése
    W szélességre. Ha valamelyik ismert placeholder jelsorozat megtalálható
    benne, a homogén-régió-kitöltés szabályát alkalmazzuk; egyébként
    folytonossági heurisztikával választunk bal- vagy jobbra-igazítás között
    (lásd alább), az előző dekódolt sorhoz (prev_row) viszonyítva.
    """
    ph_idx = None
    limit = len(raw_px) - 6
    for i in range(max(0, limit)):
        chunk = tuple(raw_px[i:i+4])
        if chunk in _PLACEHOLDER_PREFIXES:
            ph_idx = i
            break

    if ph_idx is not None and ph_idx + 7 <= len(raw_px):
        prefix = raw_px[:ph_idx]
        # A jelsorozat utáni adat végén 2 bájt "szemét" van (a következő
        # marker eleje csúszik bele a kinyert hosszba) - ezt levonjuk.
        suffix = raw_px[ph_idx+7:-2] if len(raw_px) - (ph_idx+7) >= 2 else raw_px[ph_idx+7:]
        fill_count = W - len(prefix) - len(suffix)
        if fill_count >= 0:
            fill_value = 240
            result = bytes(prefix) + bytes([fill_value]) * fill_count + bytes(suffix)
            return result[:W]

    # Típus C: rövidebb (4 bájtos) placeholder forma [A, X, B, 4], ahol
    # X = 4*row_index (pontos egyezés - ez a disambiguáló horgony, mint
    # a Típus A/B-nél), A egy kis változó szám (~17-22), B mindig 32
    # többszöröse (32-192 közötti tartományban megfigyelve). A "trail"
    # (a jelsorozat utáni szemét bájtok száma, amit a suffix végéről le
    # kell vágni) egy 4 elemű ciklikus mintát követ:
    # trail = ((B//32) - 3) % 4 (BMP-vel validálva 13 sorra, 5 különböző
    # portrén: B=96->trail=0, 128->1, 160->2, 192->3, 32->2, 64->3 -
    # a modulo-4 ciklikusság abból ered, hogy B feltehetően egy belső
    # számláló alsó bitjeit kódolja).
    target_X = 4 * row_index
    ph_idx_c = None
    for i in range(len(raw_px) - 3):
        if (raw_px[i+1] == target_X and raw_px[i+3] == 4
                and raw_px[i+2] in (32, 64, 96, 128, 160, 192)):
            ph_idx_c = i
            break

    if ph_idx_c is not None:
        A, X, B, _C = raw_px[ph_idx_c:ph_idx_c+4]
        trail = ((B // 32) - 3) % 4
        prefix = raw_px[:ph_idx_c]
        tail_start = ph_idx_c + 4
        if trail > 0 and len(raw_px) - tail_start > trail:
            suffix = raw_px[tail_start:-trail]
        else:
            suffix = raw_px[tail_start:]
        fill_count = W - len(prefix) - len(suffix)
        if fill_count >= 0:
            fill_value = 240
            result = bytes(prefix) + bytes([fill_value]) * fill_count + bytes(suffix)
            return result[:W]

    # Alapeset: nincs felismert placeholder. Először eltávolítjuk az
    # esetleges [1, 0] "szemét" 2 bájtot a végéről - ez akkor jelenik meg,
    # amikor két (vagy több) egymást követő sor is rövid, és a köztük lévő
    # marker formája [K2, 1, 0] helyett áll a várt [K2, ec_lo, ec_hi, 0]
    # forma elé (a kompresszor extra jelzést tesz a lánc folytatásakor) -
    # BMP-vel validálva (FU080S00 sor9/10/11).
    if len(raw_px) >= 2 and raw_px[-2] == 1 and raw_px[-1] == 0:
        raw_px = raw_px[:-2]

    # L00 belső (nem "235"-prefixű) rövid sor marker esete: a kinyert
    # raw_px végén egy árva "0" bájt marad (a [K2,ec_lo,0,0] négy bájtos
    # marker 3. bájtja csúszott bele, mert a marker maga nem 5 bájtos
    # "235" prefixet használ). Ezt levágjuk; a kitöltés értékét pedig
    # nem a fix 240, hanem a sorban már dekódolt pixelek leggyakoribb
    # értéke adja - ez egy keret/háttér-szín szokott lenni (BMP-vel
    # validálva: FH018L00 sor0/1 - a 240 helyett a leggyakoribb pixel
    # (itt 42) sokkal jobb közelítést ad, 87/115 -> 103/115). Megjegyzés:
    # ez a hiányzó régió valószínűleg framebuffer-szintű "nem újrarajzolt"
    # terület a játékban (a zaj/eltérés pozíciója a felhasználó
    # megfigyelése szerint változó), így itt elvi korlát van a tökéletes
    # rekonstrukcióban - ez csak a legjobb elérhető közelítés. CSAK L00-nál
    # (W=115) alkalmazzuk - S00-nál (W=55) az árva "0" gyakran a [1,0]
    # mintából vagy a tényleges pixeladatból ered, és a régi 240/
    # folytonossági logika megbízhatóbb (BMP-vel validálva: FD026S00 sor2
    # regressziót mutatott, amikor ez a heurisztika S00-ra is aktiválódott).
    if W > 55 and len(raw_px) >= 1 and raw_px[-1] == 0 and len(raw_px) < W:
        raw_px_trimmed = raw_px[:-1]
        if len(raw_px_trimmed) > 0:
            counts = {}
            for v in raw_px_trimmed:
                counts[v] = counts.get(v, 0) + 1
            common_val = max(counts.items(), key=lambda kv: kv[1])[0]
            pad = W - len(raw_px_trimmed)
            result = bytes(raw_px_trimmed) + bytes([common_val]) * pad
            return result[:W]

    # Két lehetséges igazítás van: bal (adat a sor elején, kitöltés a
    # végén) vagy jobb (kitöltés az elején, adat a sor végén) - mindkettő
    # előfordul a gyakorlatban (lásd FH011S00 sor29-31, FH014S00 sor40).
    # Folytonossági heurisztikával döntünk: az előző dekódolt sorhoz
    # (prev_row) képest melyik igazítás ad kisebb összesített abszolút
    # eltérést a megfelelő oszlopokban - ez azon alapul, hogy a portrék
    # többnyire sima, lassan változó színátmenetekből állnak, így a
    # helyes igazítás jobban "illik" a szomszédos sorhoz.
    if len(raw_px) == 0:
        return bytes(W)
    fill_value = 240
    pad = W - len(raw_px)
    left_aligned = bytes(raw_px) + bytes([fill_value]) * pad
    if pad == 0 or prev_row is None:
        return left_aligned[:W]

    right_aligned = bytes([fill_value]) * pad + bytes(raw_px)

    def _continuity_score(row):
        return sum(abs(a - b) for a, b in zip(row, prev_row))

    if _continuity_score(right_aligned) < _continuity_score(left_aligned):
        return right_aligned[:W]
    return left_aligned[:W]


def _get_trailer_bytes(hist, W, H, hp_end):
    """
    A dekompresszált stream VÉGÉN található "trailing patch block" (lezáró
    javító-blokk) kinyerése. Ez egy korábban ismeretlen struktúra, amely a
    fő soronkénti dekódolás UTÁN következik, és [235,0,0,0,128] fix fejjel
    kezdődik. Tartalma: 1) Section1 - explicit pixeladatú patch bejegyzések
    [count,p1=4*row,p2,p3]+count adatbájt (4-bájt-igazítással kitöltve),
    2) [0,0,0,128] elválasztó, 3) Section2 - 8-bájtos, soronkénti index-
    tábla bejegyzések (jelentése még nem teljesen feltárt), 4) [0,0,0,128]
    záró terminátor. Csak Section1-et használjuk jelenleg (lásd
    _parse_trailer_patches).
    """
    markers = _collect_row_markers(hist, W, H, hp_end)
    if not markers:
        return b''
    last_marker_row = max(markers.keys())
    lm, _lk = markers[last_marker_row]
    steps = (H - 1) - last_marker_row
    eo = (lm - W) + steps * (W + 5)
    tail_start = eo + W
    if tail_start < 0 or tail_start > hp_end:
        return b''
    return bytes(hist[tail_start:hp_end])


def _parse_trailer_patches(trailer, W, H):
    """
    A trailing patch block Section1 részének feldolgozása: explicit
    pixeladatú patch bejegyzések kinyerése (count, sor, p2, p3, adat).
    Az igazítást a p2/p3 mezők döntik el (lásd _apply_trailer_patches):
    ha p2==0 és p3==0, a patch a SOR ELEJÉRE kerül, egyébként a sor
    VÉGÉRE (jobbra igazítva). A bejegyzések 4 bájtra igazítva követik
    egymást (header 4 bájt + count adatbájt, majd (-(4+count))%4 nullával
    kitöltve a következő 4-es határig). Visszaad: [(row, count, p2, p3, data), ...]
    """
    entries = []
    if len(trailer) < 5 or trailer[0] != 235:
        return entries
    pos = 5
    n = len(trailer)
    while pos + 4 <= n:
        c, p1, p2, p3 = trailer[pos], trailer[pos+1], trailer[pos+2], trailer[pos+3]
        if c == 0:
            break
        if not (1 <= c <= W and p1 % 4 == 0 and 0 <= p1 // 4 < H and pos+4+c <= n):
            break
        row = p1 // 4
        data = trailer[pos+4:pos+4+c]
        entries.append((row, c, p2, p3, data))
        newpos = pos + 4 + c
        pad = (-(4 + c)) % 4
        pos = newpos + pad
    return entries


def _apply_trailer_patches(rows, entries, W):
    """A Section1 patch-eket a megfelelő sorba illeszti be, felülírva a
    korábbi (placeholder/fallback) tartalmat. Az igazítást a p2/p3 mezők
    döntik el: ha p2==0 ÉS p3==0 → a patch a SOR ELEJÉRE kerül
    (row[0:count] = data); egyébként a SOR VÉGÉRE, jobbra igazítva
    (row[W-count:W] = data). Ezt direkt BMP ground-truth összehasonlítás
    igazolta (FH006S00 sor32/35, FH014S00 sor40 - mindhárom p2=p3=0,
    és a patch adat pixel-pontosan a sor ELSŐ count bájtjával egyezik;
    minden más eddig vizsgált bejegyzésnek nemzéró p2/p3 van, és azok
    a sor VÉGÉN egyeznek)."""
    for row, count, p2, p3, data in entries:
        if row >= len(rows) or count > W or count <= 0:
            continue
        old = rows[row]
        if len(old) != W:
            continue
        if p2 == 0 and p3 == 0:
            new_row = bytes(data) + old[count:]
        else:
            new_row = old[:W-count] + bytes(data)
        rows[row] = new_row
    return rows


def _parse_trailer_section2(trailer, W, H):
    """
    A trailing patch block Section2 részének feldolgozása. Minden
    bejegyzés 8 bájt: [X, p1=4*row, p2, p3, Y, Z, 0, 0]. JELENTÉSE
    (BMP ground-truth-tal validálva, ~30 bejegyzésen, lásd a session
    jegyzeteit): ez egy LZ-stílusú "vissza-hivatkozás" - a Y,Z mezők
    EGYÜTT egy ABSZOLÚT pozíciót kódolnak a dekompresszált `hist`
    bufferben (16 bites, kis-véges: pozíció = Z*256 + Y), ahonnan X
    bájtot kell másolni a sorba. A cél-oszlopot lásd
    _apply_trailer_section2-ben.
    """
    if len(trailer) < 5 or trailer[0] != 235:
        return []
    pos = 5
    n = len(trailer)
    while pos + 4 <= n:
        c, p1 = trailer[pos], trailer[pos+1]
        if c == 0:
            break
        if not (1 <= c <= W and p1 % 4 == 0 and 0 <= p1 // 4 < H and pos+4+c <= n):
            break
        newpos = pos + 4 + c
        pad = (-(4 + c)) % 4
        pos = newpos + pad
    if trailer[pos:pos+4] != bytes([0, 0, 0, 128]):
        return []
    pos += 4
    entries = []
    while pos + 8 <= n:
        X, p1, p2, p3, Y, Z, z1, z2 = trailer[pos:pos+8]
        if X == 0 and p1 == 0:
            break
        if not (0 < X <= W and p1 % 4 == 0 and 0 <= p1 // 4 < H):
            break
        row = p1 // 4
        entries.append((row, X, p2, p3, Y, Z))
        pos += 8
    return entries


def _apply_trailer_section2(rows, entries, s1_entries, hist, W, main_patches=None):
    """
    A Section2 bejegyzések alkalmazása: X bájt másolása a `hist` buffer
    Z*256+Y abszolút pozíciójáról a sor megfelelő helyére.

    ÁLTALÁNOS SZABÁLY (5. munkamenet, finomítva - validálva FH018L00
    sor1/3/5/6 stb.): egy sor tartalma ismert "horgony" darabokból áll:
    1) a fő (per-row, _rebuild_rows_v2_with_patches által megtalált)
    explicit folt(ok), 2) a Section1 trailer foltok (bal/jobb igazítva).
    Ezeket pozíció szerint sorba rendezve, a köztük (és a sor szélein)
    maradó RÉSEKET pontosan a Section2 bejegyzések töltik ki, EREDETI
    SORRENDBEN (a rések pozíció szerint növő sorrendjében). Ha ez nem
    egyezik pontosan (rés-szám / rés-méret), a korábbi, egyszerűbb
    S1-relatív formulára esünk vissza (1 vagy 2 S1 eset, vagy ha nincs
    S1: dest = p2//32+16).
    """
    hist_bytes = bytes(hist)
    s1_by_row = {}
    for row, count, p2, p3, data in s1_entries:
        s1_by_row.setdefault(row, []).append((count, p2, p3))
    s2_by_row = {}
    for idx, (row, X, p2, p3, Y, Z) in enumerate(entries):
        s2_by_row.setdefault(row, []).append((idx, X, p2, p3, Y, Z))

    dest_by_idx = {}
    for row, group in s2_by_row.items():
        anchors = []
        if main_patches is not None and row < len(main_patches):
            for (off, K, _explicit) in main_patches[row]:
                if K < W:  # teljes sor (K>=W) esetén nincs "rés", nem horgony
                    anchors.append((off, off + K))
        for (count, p2, p3) in s1_by_row.get(row, []):
            if p2 == 0 and p3 == 0:
                anchors.append((0, count))
            else:
                anchors.append((W - count, W))
        anchors.sort()
        merged = []
        for a in anchors:
            if merged and a[0] <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], a[1]))
            else:
                merged.append(list(a))
        gaps = []
        cur = 0
        for (s, e) in merged:
            if s > cur:
                gaps.append((cur, s))
            cur = max(cur, e)
        if cur < W:
            gaps.append((cur, W))

        matched = (len(gaps) == len(group) and
                   all((g[1]-g[0]) == e[1] for g, e in zip(gaps, group)))
        if matched:
            for (idx, X, p2, p3, Y, Z), (gs, ge) in zip(group, gaps):
                dest_by_idx[idx] = gs
        else:
            s1_list = s1_by_row.get(row, [])
            if len(s1_list) == 2:
                lefts = [e for e in s1_list if e[1] == 0 and e[2] == 0]
                rights = [e for e in s1_list if not (e[1] == 0 and e[2] == 0)]
                left_count = lefts[0][0] if lefts else None
                right_count = rights[0][0] if rights else None
                for i, (idx, X, p2, p3, Y, Z) in enumerate(group):
                    if i == 0 and left_count is not None:
                        dest_by_idx[idx] = left_count
                    elif right_count is not None:
                        dest_by_idx[idx] = W - right_count - X
                    elif left_count is not None:
                        dest_by_idx[idx] = left_count
                    else:
                        dest_by_idx[idx] = p2 // 32 + 16
            elif len(s1_list) == 1:
                s1_count, s1_p2, s1_p3 = s1_list[0]
                for idx, X, p2, p3, Y, Z in group:
                    if s1_p2 == 0 and s1_p3 == 0:
                        dest_by_idx[idx] = s1_count
                    else:
                        dest_by_idx[idx] = W - s1_count - X
            else:
                for idx, X, p2, p3, Y, Z in group:
                    dest_by_idx[idx] = p2 // 32 + 16

    for idx, (row, X, p2, p3, Y, Z) in enumerate(entries):
        if row >= len(rows) or X <= 0 or X > W:
            continue
        srcpos = Z * 256 + Y
        if srcpos < 0 or srcpos + X > len(hist_bytes):
            continue
        copied = hist_bytes[srcpos:srcpos+X]
        old = rows[row]
        if len(old) != W:
            continue
        dest = dest_by_idx.get(idx, p2 // 32 + 16)
        dest = max(0, min(dest, W - X))
        new_row = old[:dest] + copied + old[dest+X:]
        rows[row] = new_row
    return rows


def read_portraits(dbi_path, init_codes):
    """Az összes FD portré beolvasása UNIT.DBI-ból."""
    with open(dbi_path,'rb') as f: data=f.read()
    portraits=[]; last_pal=[(0,0,0)]*256; p=0

    while True:
        pp=data.find(b'MQRC',p)
        if pp==-1: break
        bt=struct.unpack_from('<I',data,pp+8)[0]

        if bt==2:  # paletta blokk
            last_pal=[]
            for i in range(256):
                B=data[pp+28+i*4]; G=data[pp+28+i*4+1]; R=data[pp+28+i*4+2]
                last_pal.append((R,G,B))

        elif bt>=164:
            W=data[pp+40]; H=data[pp+42]
            if W in (55,115) and H==67:
                sA=struct.unpack_from('<I',data,pp+12)[0]
                hp_end=data[pp+37]|(data[pp+38]<<8)
                stream=data[pp+48:pp+28+sA]
                name=data[pp+28:pp+36].rstrip(b'\x00').decode('ascii','replace')

                hist,hp=decompress(stream,init_codes,hp_end)
                if W == 115:
                    # ÚJ, validált algoritmus L00-hoz (2026-06-18, 5. munkamenet):
                    # lásd _rebuild_rows_v2 dokumentációját. Minden sor előtt
                    # egy [K,p1=4*sor,p2,p3] jelző áll; K<W esetén
                    # offset=p3*8+p2//32 (validálva ~20+ mintán 100%-os
                    # egyezéssel), a jelzőn kívüli oszlopok az előző sorból
                    # öröklődnek (közelítés).
                    rows, _all_patches = _rebuild_rows_v2_with_patches(hist, W, H, hp)
                    rows = [bytes(r) for r in rows]
                else:
                    # RÉGI, S00-ra finomhangolt heurisztika (pozíció-konzisztens
                    # marker gyűjtés + kétfázisú rövid sor lánc keresés - lásd
                    # _collect_row_markers / _find_short_row_pad). MEGTARTVA,
                    # mert az új algoritmus S00-nál regressziót okozott
                    # (99.45% -> ~95%) - valószínűleg az S00-specifikus
                    # placeholder-mintákra (_PLACEHOLDER_PREFIXES) van szükség,
                    # amit az új algoritmus nem ismer.
                    _ec_offset = 1
                    rows=[]
                    sorted_markers=sorted(_collect_row_markers(hist,W,H,hp_end).items())
                    r=0; midx=0
                    while r<H:
                        if midx<len(sorted_markers) and sorted_markers[midx][0]==r:
                            _mrow,(_mpos,_K)=sorted_markers[midx]; midx+=1
                            _rs=_mpos-W
                            px=bytes(hist[max(0,_rs):_mpos])
                            if len(px)<W: px=px+bytes(W-len(px))
                            rows.append(px[:W]); r+=1
                            if _K<W:
                                _pos=_mpos+5; _cr=r
                                while _cr<H:
                                    _ec_full=4*(_cr+_ec_offset)
                                    _result=_find_short_row_pad(hist,_pos,_ec_full,W,hp_end)
                                    if _result is None: break
                                    _k,_K2,_newpos,_is_tail=_result
                                    _spx=bytes(hist[_pos:_pos+_k])
                                    if _is_tail:
                                        rows.append(_reconstruct_short_row(_spx,_cr,W,rows[-1] if rows else None))
                                        _cr+=1; r+=1
                                        if _cr>=H: break
                                        _next_ec=4*(_cr+_ec_offset)
                                        _next_result=_find_short_row_pad(hist,_newpos,_next_ec,W,hp_end)
                                        if _next_result is not None and _next_result[0]<W:
                                            _pos=_newpos
                                            continue
                                        _npx=bytes(hist[_newpos:_newpos+W])
                                        if len(_npx)<W: _npx=_npx+bytes(W-len(_npx))
                                        rows.append(_npx[:W]); _cr+=1; r+=1
                                        _pos=_newpos+W
                                        continue
                                    rows.append(_reconstruct_short_row(_spx,_cr,W,rows[-1] if rows else None))
                                    _pos=_newpos; _cr+=1; r+=1
                                    if _K2==W: break
                        else:
                            if rows and midx>0:
                                _lr,(_lm,_lk)=sorted_markers[min(midx-1,len(sorted_markers)-1)]
                                _steps=r-_lr
                                _eo=(_lm-W)+_steps*(W+5)
                                rows.append(bytes(hist[max(0,_eo):_eo+W]))
                            else:
                                rows.append(bytes(W))
                            r+=1

                    # HIBRID (5. munkamenet, 3.10 szakasz, finomítva): az új,
                    # validált több-foltos algoritmust is lefuttatjuk, és
                    # MINDEN megtalált foltot (akár csak 1-et is - minden
                    # folt bájtra pontos, validált explicit adat, sosem
                    # közelítés) OSZLOP-SZINTEN felülírjuk a régi heurisztika
                    # eredményén. A foltok által NEM lefedett oszlopoknál a
                    # régi heurisztika (placeholder/igazítás-logika) marad,
                    # mivel az jobb közelítést ad, mint a naiv "előző sorból
                    # öröklés" (validálva: FN127S00 sor40 - 1 folt, [32,55),
                    # bájtra pontos; a [0,32) tartományban a régi heurisztika
                    # eredménye marad).
                    _new_rows, _all_patches = _rebuild_rows_v2_with_patches(hist, W, H, hp)
                    rows = [bytearray(row) for row in rows]
                    for _ri in range(min(H, len(rows))):
                        for _off, _K, _explicit in _all_patches[_ri]:
                            rows[_ri][_off:_off+_K] = bytes(_explicit)
                    rows = [bytes(row) for row in rows]

                _trailer = _get_trailer_bytes(hist, W, H, hp_end)
                _patches = _parse_trailer_patches(_trailer, W, H)
                if _patches:
                    rows = _apply_trailer_patches(list(rows), _patches, W)
                _s2patches = _parse_trailer_section2(_trailer, W, H)
                if _s2patches:
                    rows = _apply_trailer_section2(list(rows), _s2patches, _patches, hist, W, _all_patches)

                portraits.append({
                    'name':name,'bt':bt,'W':W,'H':H,
                    'rows':rows,'palette':list(last_pal),
                    'pp':pp,'sA':sA,'hp_end':hp_end,
                    'trailer_patches':_patches,'trailer_section2':_s2patches
                })
        p=pp+1
    return portraits, data

def _minimal_row_patch(row, prev_row, W):
    """Visszaadja a (offset, K) párt: a legkisebb összefüggő [offset,offset+K)
    tartományt, amin KÍVÜL a `row` pontosan megegyezik a `prev_row`-val.
    Ha prev_row is None (első sor): (0, W) - teljes sor explicit.

    FONTOS: K=0 SOHA nem megengedett, még ha a sor TELJESEN egyezik is az
    előzővel! Ennek oka: K=0 esetén a dekóder offset-ellenőrzése
    (0<=offset<=W-K) MINDIG igaz (W-0=W), tehát egy K=0 jelző GYAKORLATILAG
    SZŰRÉS NÉLKÜL elfogadásra kerül - ez véletlen hamis találatokhoz vezet
    a "következő folt keresése" logikában, ha a pixeladatban PUSZTÁN
    VÉLETLENÜL előfordul egy [0, target_ctr] bájtpár (validálva: FH008S00
    sor64 - egy hamis K=0 találat a sor65 pixeladatában teljesen
    eltüntette sor65 és sor66 helyes dekódolását). Ha a sor teljesen
    egyezik az előzővel, K=1-et írunk (egyetlen, tetszőleges - itt: az
    első - oszlop explicit duplikálásával), ami elenyésző méretnövekedés
    árán garantáltan elkerüli ezt a kockázatot.
    """
    if prev_row is None:
        return (0, W)
    lead = 0
    while lead < W and row[lead] == prev_row[lead]:
        lead += 1
    if lead == W:
        return (0, 1)  # teljesen egyezik - minimális, biztonságos K=1
    trail = 0
    while trail < W - lead and row[W-1-trail] == prev_row[W-1-trail]:
        trail += 1
    offset = lead
    K = W - lead - trail
    return (offset, K)


def _multi_row_patches(row, prev_row, W, min_gap=6):
    """Visszaadja az [(offset,K), ...] listát: az ELŐZŐ sorhoz képest eltérő
    "szigetek" mindegyikét KÜLÖN foltként (validálva: a natív formátum
    soronként TÖBB [K,p1,p2,p3] foltot is megenged, lásd 3.9 szakasz).
    Ha két eltérő szigetet kevesebb, mint `min_gap` egyező oszlop választ
    el, összevonjuk egyetlen folttá (a 4 bájtos jelző-overhead miatt ez
    kisebb össz. méretet ad, mint két külön folt). Ha prev_row None
    (első sor): [(0, W)] - teljes sor explicit.
    """
    if prev_row is None:
        return [(0, W)]
    diff = [row[c] != prev_row[c] for c in range(W)]
    if not any(diff):
        return [(0, 1)]  # teljesen egyezik - minimális, biztonságos K=1
    islands = []
    c = 0
    while c < W:
        if diff[c]:
            start = c
            while c < W and diff[c]:
                c += 1
            islands.append([start, c])  # [start, end)
        else:
            c += 1
    # Kis rések összevonása (overhead-csökkentés)
    merged = [islands[0]]
    for s, e in islands[1:]:
        if s - merged[-1][1] < min_gap:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    return [(s, e - s) for s, e in merged]


def make_hist_buffer(rows, W, H):
    """Nyers history buffer az enkóderhez (v2.2 - natív struktúrát követő,
    VÁLTOZÓ HOSSZÚ sorokkal, TÖBB-FOLTOS kódolással, ÖNELLENŐRZŐ build-dal).

    KORÁBBI BUGOK:
    - v2.0: minden sor TELJES (K=W) hosszúsággal, FIX stride-dal (W+5) lett
      beírva, ami nem egyezett a natív struktúrával -> a játék natív
      dekódere zajt/crash-t produkált.
    - v2.1: minden sorhoz EGYETLEN, összefüggő explicit foltot generáltunk
      (a legkisebb [offset,offset+K) tartomány, ami lefedi az ÖSSZES eltérő
      oszlopot az előző sorhoz képest). Ez helyes volt, de SZÉTSZÓRT
      eltérések esetén (különösen széles, L00 portréknál) feleslegesen
      NAGY foltot eredményezett (a két szélső eltérés közötti, valójában
      EGYEZŐ rész is belekerült az explicit adatba) - ez a stream-et
      gyakran a natív slot méreténél NAGYOBBÁ tette.

    v2.2: minden sorhoz a VALÓDI eltérés-"szigeteket" KÜLÖN foltként
    kódoljuk (lásd _multi_row_patches) - validálva a 3.9 szakasz
    felfedezésével, hogy egy sor TÖBB [K,p1,p2,p3] foltot is tartalmazhat,
    ugyanazzal a p1 (=4*sor_index) értékkel.

    Minden sor szerkezete a lineáris bufferben:
      (sor>0 esetén, MINDEN folt előtt:) [235 prefix]
      [K] [p1=(4*r)%256] [p2] [p3]
      [K darab explicit pixel bájt]
      (a sor TOVÁBBI foltjai ugyanígy, egymás után, UGYANAZZAL a p1-gyel)
    ahol K<W esetén offset = p3*8 + p2//32, K==W esetén a K bájt a TELJES
    sor (p2=p3=0, csak egyetlen folt lehetséges ekkor).

    ÖNELLENŐRZÉS (kritikus, lásd v2.1 dokumentáció): minden buffer-épités
    UTÁN visszadekódoljuk a saját validált dekóderünkkel; minden sort, ami
    nem egyezik pontosan (pl. véletlen hamis folt-találat a pixeladatban),
    TELJES (K=W) sorra kényszerítünk, és újraépítünk, amíg minden sor
    pontosan egyezik.
    """
    def build(force_full):
        buf = bytearray()
        prev_row = None
        for r in range(H):
            row = bytes(rows[r][:W])
            ctr = 4 * r
            p1 = ctr % 256
            # 64+ soros portreknal (H>64) a p1 (1 bajtos, %256) mezo
            # 64 soronkent ismetlodik (4*64=256=0 mod 256) -- ez a
            # jatekban felcsuszast okoz (empirikusan validalva: a 64-66.
            # sor adata a 0-2. sor helyere kerul). A _collect_row_markers
            # regi heurisztika mar dokumentalta ezt ("64+ soros portreknal
            # ... 8-bites tulcsordulas"), 2-bajtos (p1=LO, p2 BIT0=HI)
            # counter-kent kezelve. FIX: a p2 mezo LEGALACSONYABB BITJEBE
            # (bit0) irjuk a felso bitet (ctr>>8)&1 - ez NEM zavarja a
            # K<W eseten hasznalt offset-formulat (offset=p3*8+p2//32,
            # csak a p2 5-7. bitjeit hasznalja, a bit0-4 szabad).
            hi_bit = (ctr >> 8) & 1
            if r in force_full or prev_row is None:
                if r > 0:
                    buf += bytes([235])
                buf += bytes([W, p1, hi_bit, 0])
                buf += row
            else:
                patches = _multi_row_patches(row, prev_row, W)
                for offset, K in patches:
                    buf += bytes([235])
                    if K >= W:
                        buf += bytes([W, p1, hi_bit, 0]); buf += row
                    else:
                        p3 = offset // 8
                        p2 = (offset % 8) * 32 | hi_bit
                        buf += bytes([K, p1, p2, p3])
                        buf += row[offset:offset+K]
            prev_row = row
        trailer = bytes([235, 0, 0, 0, 128, 0, 0, 0, 128, 0, 0, 0, 128])
        buf += trailer
        return buf, len(buf)

    # FONTOS (2026-06-19, in-game teszttel validálva): a foltos/öröklős
    # ("inherit from previous row") kódolás a JÁTÉK valódi rendererében
    # NEM ugyanazt csinálja, mint a mi PURE dekóderünk - in-game zajt
    # okozott pontosan azokon az oszlopokon, amiket a foltrendszer
    # "örökítésre" hagyott. A saját önellenőrzésünk ezt soha nem fogta
    # volna ki, mert a MI dekóderünk helyesen kezeli az öröklést - csak
    # a NATÍV nem. Amíg nem találjuk meg a valódi öröklés-szabályt, MINDEN
    # sort TELJESEN explicit (K=W) módon írunk - ez korrekt, validált
    # in-game eredményt ad, a tömörítési hatékonyság rovására.
    force_full = set(range(H))
    for _ in range(H + 2):  # legfeljebb H+2 iteráció - garantáltan konvergál
        buf, hp_end = build(force_full)
        check_rows, _ = _rebuild_rows_v2_with_patches(buf, W, H, hp_end)
        bad = [r for r in range(H) if bytes(check_rows[r]) != bytes(rows[r][:W])]
        if not bad:
            return bytearray(buf), hp_end
        force_full.update(bad)
    # Biztonsági végső próba: minden sor teljes (mindig helyes kell legyen)
    buf, hp_end = build(set(range(H)))
    return bytearray(buf), hp_end

def build_mqrc(compressed, W, H, bt, name, hp_end):
    """MQRC blokk összerakása.
    KRITIKUS mezők:
      [16..19] = sA másolata (nélkül: üres portré a játékban!)
      [20..23] = 1 flag (nélkül: üres portré a játékban!)
    """
    sA=20+len(compressed)
    hdr=bytearray(48)
    hdr[0:4]=b'MQRC'
    struct.pack_into('<I',hdr,8,bt)
    struct.pack_into('<I',hdr,12,sA)
    struct.pack_into('<I',hdr,16,sA)   # sA MÁSOLATA - kötelező!
    struct.pack_into('<I',hdr,20,1)    # flag=1 - kötelező!
    hdr[37]=hp_end&0xFF; hdr[38]=(hp_end>>8)&0xFF
    hdr[44]=hdr[37]; hdr[45]=hdr[38]
    hdr[40]=W; hdr[42]=H
    nb=name.encode('ascii')[:8]; hdr[28:28+len(nb)]=nb
    return bytes(hdr)+compressed

# ─── Kép I/O (Pillow) ─────────────────────────────────────────────────────────

def save_portrait_png(rows, palette, W, H, path):
    """Portré mentése RGBA PNG-be (Pillow)."""
    try:
        from PIL import Image
    except ImportError:
        print("  [!] Pillow nincs telepítve: pip install pillow")
        print(f"  Pixel adatok: {W}x{H}, paletta: {len(palette)} szín")
        return
    img=Image.new('P',(W,H))
    flat_pal=[]
    for r,g,b in palette: flat_pal+=[r,g,b]
    img.putpalette(flat_pal)
    px=bytearray()
    for row in rows: px+=bytes(row[:W])
    img.frombytes(bytes(px))
    img.save(path)

def load_portrait_png(path, palette):
    """PNG betöltése palettás pixelekként.
    
    A kép palettájából megkeresi a legjobb egyezést a DBI palettával.
    """
    try:
        from PIL import Image
    except ImportError:
        sys.exit("Hiba: pip install pillow")
    img=Image.open(path)
    W,H=img.size

    # Palettás mód: közvetlen használat
    if img.mode=='P':
        px=list(img.tobytes())
        rows=[bytes(px[r*W:(r+1)*W]) for r in range(H)]
        return rows, W, H

    # RGB(A) → legközelebbi paletta szín
    img=img.convert('RGB')
    px=list(img.tobytes())
    rows=[]
    for r in range(H):
        row=bytearray()
        for c in range(W):
            ri,gi,bi=px[(r*W+c)*3],px[(r*W+c)*3+1],px[(r*W+c)*3+2]
            best_i=0; best_d=10**9
            for i,(rp,gp,bp) in enumerate(palette):
                d=(ri-rp)**2+(gi-gp)**2+(bi-bp)**2
                if d<best_d: best_d=d; best_i=i
            row.append(best_i)
        rows.append(bytes(row))
    return rows, W, H

# ─── Parancssori kezelő ───────────────────────────────────────────────────────

def cmd_list(dbi_path, imggrab_path):
    init_codes=load_init_codes(imggrab_path)
    portraits,_=read_portraits(dbi_path,init_codes)
    print(f"{'Név':<12} {'Típus':>6} {'Méret':>8}  Pozíció")
    print('-'*40)
    for p in portraits:
        size='S' if p['W']==55 else 'L'
        print(f"{p['name']:<12} bt={p['bt']:>4}  {p['W']}×{p['H']} ({size})  @{p['pp']:#08x}")
    print(f"\nÖsszesen: {len(portraits)} portré")

def cmd_decode(dbi_path, out_dir, imggrab_path):
    Path(out_dir).mkdir(parents=True,exist_ok=True)
    init_codes=load_init_codes(imggrab_path)
    portraits,_=read_portraits(dbi_path,init_codes)
    for p in portraits:
        out=os.path.join(out_dir,f"{p['name']}.png")
        save_portrait_png(p['rows'],p['palette'],p['W'],p['H'],out)
        print(f"  {p['name']}.png  ({p['W']}×{p['H']})")
    print(f"\n{len(portraits)} portré kimentve → {out_dir}")

def read_dbi_toc(data, header_toc_ptr_offset=24):
    """A fájl végi abszolút-offsetes TOC beolvasása.
    Visszaadja: (toc_start, count, entries), ahol entries[0] a fejléc-sor
    (offset mezője=count, nem valódi offset), entries[1..count] a valódi
    bejegyzések: {'off','offset','next_bt','next_sA','next_sA2'}.
    """
    toc_start = struct.unpack_from('<I', data, header_toc_ptr_offset)[0]
    count = struct.unpack_from('<I', data, toc_start)[0]
    n = count + 1
    vals = struct.unpack_from('<%dI' % (n * 4), data, toc_start)
    entries = []
    for i in range(0, n * 4, 4):
        entries.append({'off': toc_start + i * 4, 'offset': vals[i],
                         'next_bt': vals[i + 1], 'next_sA': vals[i + 2], 'next_sA2': vals[i + 3]})
    return toc_start, count, entries


def resize_patch_toc(orig_data, pp, old_size, mqrc, header_toc_ptr_offset=24):
    """Egy MQRC blokk lecserélése MÁS méretű (akár hosszabb) tartalomra,
    a fájl végi TOC (és a globális fejléc TOC-pointere) konzisztens
    frissítésével. Validálva: a célblokk után lévő összes blokk offsetje
    eltolódik a méretkülönbséggel, a megelőző TOC-bejegyzés next_sA
    gyorsítótár-mezője frissül, a TOC saját pozíciója (és a rá mutató
    globális pointer) is helyesen követi a fájl méretváltozását.
    """
    new_size = len(mqrc)
    size_diff = new_size - old_size
    toc_start, count, entries = read_dbi_toc(orig_data, header_toc_ptr_offset)
    matches = [i for i in range(1, len(entries)) if entries[i]['offset'] == pp]
    if len(matches) != 1:
        raise ValueError(f"Nem találom egyértelműen a blokkot a TOC-ban (pp={pp}, matches={matches})")
    k = matches[0]

    new_data = bytearray(orig_data[:pp] + mqrc + orig_data[pp + old_size:])

    # Az új sA-t mindig a frissen beírt blokk SAJÁT fejlécéből olvassuk vissza
    # (nem külön formulából számoljuk), hogy elkerüljük az elcsúszás-kockázatot.
    new_sA = struct.unpack_from('<I', new_data, pp + 12)[0]

    # 1. globális TOC-pointer a fájl fejlécében
    old_ptr = struct.unpack_from('<I', new_data, header_toc_ptr_offset)[0]
    struct.pack_into('<I', new_data, header_toc_ptr_offset, old_ptr + size_diff)

    # 2. minden TOC-bejegyzés offsetje, ami a módosított blokk UTÁN mutatott
    for i in range(1, len(entries)):
        e = entries[i]
        phys_pos = e['off'] + size_diff  # a bejegyzés saját, eltolt fizikai pozíciója
        if e['offset'] > pp:
            struct.pack_into('<I', new_data, phys_pos, e['offset'] + size_diff)

    # 3. a megelőző (tömb-sorrendben) bejegyzés next_sA/next_sA2 gyorsítótára
    prev = entries[k - 1]
    prev_phys = prev['off'] + size_diff
    struct.pack_into('<I', new_data, prev_phys + 8, new_sA)
    struct.pack_into('<I', new_data, prev_phys + 12, new_sA)

    return bytes(new_data)


def verify_dbi_toc(data, header_toc_ptr_offset=24):
    """Diagnosztikai ellenőrzés: minden TOC-bejegyzés offsetje valódi MQRC
    blokkra mutat-e, és a next_bt/next_sA gyorsítótár-mezők egyeznek-e a
    tényleges következő blokk adataival. Visszaadja a hibás bejegyzések listáját.
    """
    toc_start, count, entries = read_dbi_toc(data, header_toc_ptr_offset)
    positions = set(m.start() for m in re.finditer(b'MQRC', data))
    bad = []
    for i in range(1, len(entries)):
        e = entries[i]
        if e['offset'] not in positions:
            bad.append(('bad_offset', i, e))
            continue
        bt = struct.unpack_from('<I', data, e['offset'] + 8)[0]
        sA = struct.unpack_from('<I', data, e['offset'] + 12)[0]
        prev = entries[i - 1]
        if prev['next_bt'] != bt or prev['next_sA'] != sA or prev['next_sA2'] != sA:
            bad.append(('bad_link', i, prev, bt, sA))
    return bad


def _scan_all_blocks(data):
    """Az összes MQRC blokk (bt, name) párjának összegyűjtése a fájlból."""
    out = []
    p = 0
    while True:
        pp = data.find(b'MQRC', p)
        if pp == -1:
            break
        bt = struct.unpack_from('<I', data, pp + 8)[0]
        name = data[pp + 28:pp + 36].rstrip(b'\x00').decode('ascii', 'replace')
        out.append((pp, bt, name))
        p = pp + 1
    return out


def read_name_index_block(data):
    """A fájl elején (a 28 bájtos globális fejléc UTÁN, fix pp=28 pozíción)
    lévő NÉV→bt index-tábla beolvasása.

    Ez egy KÜLÖN MQRC-blokk (a kísérleti felfedezés szerint jellemzően bt=3),
    aminek a teste 16 bájtos bejegyzésekből áll: [8 bájt név][4 bájt nulla]
    [4 bájt bt (uint32 LE)], NÉV SZERINT ALFABETIKUSAN RENDEZVE. A motor
    feltehetően ezen keresztül oldja fel a portrénevet bt-re (bináris
    kereséshez illő rendezett struktúra) - ez FÜGGETLEN a fájl végi
    lánc-TOC-tól, amit a resize_patch_toc/read_dbi_toc kezel.

    Visszaadja: (pp, header(28 bájt nyers), bt, flag, old_sA, entries),
    ahol entries = [(name:str, bt:int), ...] alfabetikus sorrendben.
    """
    pp = 28  # mindig közvetlenül a globális fejléc után
    if data[pp:pp + 4] != b'MQRC':
        raise ValueError(f"Nem MQRC blokk a pp={pp} pozíción - a fájlformátum eltér a várttól.")
    header = bytes(data[pp:pp + 28])
    bt = struct.unpack_from('<I', header, 8)[0]
    sA = struct.unpack_from('<I', header, 12)[0]
    sA2 = struct.unpack_from('<I', header, 16)[0]
    flag = struct.unpack_from('<I', header, 20)[0]
    if sA != sA2:
        raise ValueError("A index-blokk sA és sA-másolat mezője nem egyezik - váratlan formátum.")
    if sA % 16 != 0:
        raise ValueError(f"A index-blokk mérete ({sA}) nem osztható 16-tal - nem a várt 16-bájtos bejegyzés-formátum.")
    body_start = pp + 28
    n = sA // 16
    entries = []
    for i in range(n):
        o = body_start + i * 16
        name = data[o:o + 8].rstrip(b'\x00').decode('ascii', 'replace')
        ebt = struct.unpack_from('<I', data, o + 12)[0]
        entries.append((name, ebt))
    return pp, header, bt, flag, sA, entries


def build_name_index_block(header, bt, flag, entries_sorted):
    """Új index-blokk byte-sorozat összerakása a (név,bt) lista alapján.
    entries_sorted: már alfabetikusan rendezett [(name, bt), ...] lista.
    """
    new_sA = len(entries_sorted) * 16
    new_header = bytearray(header)
    struct.pack_into('<I', new_header, 8, bt)
    struct.pack_into('<I', new_header, 12, new_sA)
    struct.pack_into('<I', new_header, 16, new_sA)
    struct.pack_into('<I', new_header, 20, flag)
    body = bytearray()
    for name, ebt in entries_sorted:
        nb = name.encode('ascii')[:8].ljust(8, b'\x00')
        body += nb + bytes(4) + struct.pack('<I', ebt)
    return bytes(new_header) + bytes(body)


def insert_into_name_index(orig_data, new_name, new_bt):
    """A kezdő név-index táblába beszúrja az (új_név,új_bt) bejegyzést a
    megfelelő alfabetikus helyre, és a resize_patch_toc segítségével
    konzisztensen eltolja/frissíti a fájl többi részét (+16 bájt).

    Visszaadja az új, teljes fájl-byte-sorozatot.
    """
    pp, header, bt, flag, old_sA, entries = read_name_index_block(orig_data)
    names = {nm for nm, _ in entries}
    if new_name in names:
        raise ValueError(f"A '{new_name}' név már szerepel a kezdő név-index táblában.")
    new_entries = sorted(entries + [(new_name, new_bt)], key=lambda e: e[0])
    new_block = build_name_index_block(header, bt, flag, new_entries)
    old_size = 28 + old_sA
    new_data = resize_patch_toc(orig_data, pp, old_size, new_block)
    return new_data


def verify_name_index(data):
    """Diagnosztika: a kezdő név-index tábla
    (1) alfabetikusan rendezett-e (nincs sorrend-hiba),
    (2) nincs duplikált név,
    (3) minden bejegyzés bt-je egyezik-e a tényleges blokk valódi bt-jével,
    (4) minden bejegyzéshez van-e tényleges MQRC blokk a fájlban.
    Visszaadja a hibák listáját (üres lista = rendben)."""
    pp, header, bt, flag, sA, entries = read_name_index_block(data)
    problems = []
    names_seen = set()
    for i, (name, ebt) in enumerate(entries):
        if name in names_seen:
            problems.append(('duplicate_name', i, name))
        names_seen.add(name)
        if i > 0 and entries[i - 1][0] >= name:
            problems.append(('sort_order', i, entries[i - 1][0], name))
    # valódi blokkok bt/név ellenőrzése
    real = {}
    p = 0
    while True:
        rp = data.find(b'MQRC', p)
        if rp == -1:
            break
        rbt = struct.unpack_from('<I', data, rp + 8)[0]
        rname = data[rp + 28:rp + 36].rstrip(b'\x00').decode('ascii', 'replace')
        real[rname] = rbt
        p = rp + 1
    for i, (name, ebt) in enumerate(entries):
        if name not in real:
            problems.append(('missing_block', i, name))
        elif real[name] != ebt:
            problems.append(('bt_mismatch', i, name, ebt, real[name]))
    return problems


def _generate_new_name_and_bt(data, W, H, prefix='GP', forced_idx=None):
    """Ütközésmentes új név (pl. 'GP004S00') és új bt-érték generálása.
    Ha forced_idx meg van adva, azt az indexet próbálja használni (hibával
    leáll, ha az így kapott név már foglalt - ez szándékos, hogy a kísérleti
    tesztek ne csússanak el észrevétlenül egy másik indexre)."""
    suffix = 'S00' if W == 55 else ('L00' if W == 115 else None)
    if suffix is None:
        sys.exit(f"Insert mód csak 55×67 (S00) vagy 115×67 (L00) méretű képet támogat, ez {W}×{H}.")

    blocks = _scan_all_blocks(data)
    used_names = {nm for _, _, nm in blocks}
    used_bts = {bt for _, bt, _ in blocks}

    if forced_idx is not None:
        name = f"{prefix}{forced_idx:03d}{suffix}"
        if name in used_names:
            sys.exit(f"A '{name}' név már foglalt a fájlban - válassz másik indexet.")
    else:
        idx = 1
        pattern = re.compile(r'^' + re.escape(prefix) + r'(\d{3})' + re.escape(suffix) + r'$')
        used_idx = [int(m.group(1)) for _, _, nm in blocks if (m := pattern.match(nm))]
        if used_idx:
            idx = max(used_idx) + 1
        name = f"{prefix}{idx:03d}{suffix}"
        while name in used_names:  # extra biztonsági kör, ha valamiért mégis ütközne
            idx += 1
            name = f"{prefix}{idx:03d}{suffix}"

    new_bt = max(used_bts) + 1
    return name, new_bt


def cmd_insert(img_path, dbi_path, imggrab_path, prefix='GP', forced_idx=None):
    """KÍSÉRLETI: teljesen ÚJ portré beszúrása a fájl végére (a meglévő
    blokkok UTÁN, a TOC elé), automatikusan generált névvel és bt-vel,
    a fájl végi TOC megfelelő bővítésével.

    FONTOS KORLÁTOZÁS: ez csak azt garantálja, hogy a DBI-fájl belsőleg
    konzisztens marad (a motor a fájlt sérülésmentesen tudja végigolvasni).
    Azt, hogy a játék valahol ténylegesen HASZNÁLJA-e ezt az új portrét
    (pl. egy egység-definíció hivatkozik-e rá névvel), ez a funkció NEM
    biztosítja - ahhoz külön, a DBI-n kívüli hivatkozást kell beállítani.
    """
    init_codes = load_init_codes(imggrab_path)
    with open(dbi_path, 'rb') as f:
        orig_data = f.read()

    # Globális paletta: az utolsó bt==2 (paletta) blokk a fájlban
    palette = None
    p = 0
    while True:
        pp = orig_data.find(b'MQRC', p)
        if pp == -1:
            break
        bt = struct.unpack_from('<I', orig_data, pp + 8)[0]
        if bt == 2:
            palette = [(orig_data[pp + 28 + i * 4 + 2], orig_data[pp + 28 + i * 4 + 1], orig_data[pp + 28 + i * 4])
                       for i in range(256)]
        p = pp + 1
    if palette is None:
        sys.exit("Nem találtam paletta-blokkot (bt==2) a fájlban.")

    print(f"Kép betöltése: {img_path}")
    rows, W, H = load_portrait_png(img_path, palette)
    if H != 67:
        sys.exit(f"Méret hiba: a kép magassága {H}, de 67 kell legyen.")

    name, new_bt = _generate_new_name_and_bt(orig_data, W, H, prefix, forced_idx)
    print(f"  Generált név: {name}  (bt={new_bt})")

    print(f"Tömörítés ({W}×{H})...")
    buf, hp_end = make_hist_buffer(rows, W, H)
    compressed = compress(buf, init_codes)
    mqrc = build_mqrc(compressed, W, H, new_bt, name, hp_end)

    # 1. lépés (ÚJ a v2.9-ben): a kezdő NÉV-INDEX tábla bővítése a megfelelő
    # alfabetikus helyre - ez a motor által (feltehetően) használt
    # név→bt feloldó struktúra, FÜGGETLEN a lánc-TOC-tól. Ennek hiánya volt
    # az oka, hogy a v2.8-as insert fájl-szinten konzisztens volt, de a
    # játék mégsem ismerte fel az új portrét.
    print(f"  Név-index tábla bővítése ('{name}' beszúrása alfabetikus helyre)...")
    data_after_index = insert_into_name_index(orig_data, name, new_bt)
    print(f"  (a végső, teljes fájl-szintű név-index ellenőrzés a mentés után következik)")

    # 2. lépés: az ÚJ portré-blokk hozzáfűzése a (már index-bővített) fájl
    # végére, a lánc-TOC megfelelő bővítésével - ugyanaz a logika, mint
    # a v2.8-ban, csak már a frissített `data_after_index`-en dolgozva.
    toc_start, count, entries = read_dbi_toc(data_after_index)
    new_sA = struct.unpack_from('<I', mqrc, 12)[0]
    new_block_offset = toc_start  # az új blokk pontosan a régi TOC helyén kezdődik

    entries[count]['next_bt'] = new_bt
    entries[count]['next_sA'] = new_sA
    entries[count]['next_sA2'] = new_sA

    new_entry = {'offset': new_block_offset, 'next_bt': 0, 'next_sA': 0, 'next_sA2': 0}
    entries.append(new_entry)
    entries[0]['offset'] = count + 1  # a fejléc-sor "offset" mezője = bejegyzésszám

    toc_bytes = b''.join(
        struct.pack('<4I', e['offset'], e['next_bt'], e['next_sA'], e['next_sA2']) for e in entries
    )

    new_data = bytearray(data_after_index[:toc_start] + mqrc + toc_bytes)
    struct.pack_into('<I', new_data, 24, toc_start + len(mqrc))  # globális TOC-pointer

    out_path = dbi_path.replace('.DBI', '_mod.DBI').replace('.dbi', '_mod.dbi')
    if out_path == dbi_path:
        out_path = dbi_path + '.mod'
    with open(out_path, 'wb') as f:
        f.write(bytes(new_data))
    print(f"  Mentve: {out_path}  (fájlméret {len(orig_data)} → {len(new_data)} bájt, "
          f"+{len(new_data)-len(orig_data)})")

    bad = verify_dbi_toc(bytes(new_data))
    bad_new = [b for b in bad if not (b[0] == 'bad_link' and b[2].get('next_bt') == 197)]
    print(f"  Lánc-TOC ellenőrzés: {'OK' if not bad_new else f'{len(bad_new)} gyanús bejegyzés!'}")

    idx_problems_final = verify_name_index(bytes(new_data))
    print(f"  Név-index ellenőrzés (végső fájlon): {'OK' if not idx_problems_final else idx_problems_final}")

    hist_v, hp_v = decompress(compressed, init_codes, hp_end)
    rows_v, _ = _rebuild_rows_v2_with_patches(hist_v, W, H, hp_v)
    ok = all(bytes(rows_v[r]) == bytes(rows[r][:W]) for r in range(H))
    print(f"  Pixel egyezés: {'100% OK ✓' if ok else 'HIBA!'}")
    print(f"\n  ÚJ PORTRÉ NEVE: {name}")
    return name


def cmd_encode(img_path, dbi_path, target_name, imggrab_path):
    init_codes=load_init_codes(imggrab_path)
    portraits,orig_data=read_portraits(dbi_path,init_codes)

    # Célportré megkeresése
    target=[p for p in portraits if p['name'].startswith(target_name)]
    if not target:
        names=[p['name'] for p in portraits]
        sys.exit(f"Nincs '{target_name}' nevű portré.\nElérhető nevek: {names[:5]}...")
    tgt=target[0]

    # Kép betöltése
    print(f"Kép betöltése: {img_path}")
    rows,W,H=load_portrait_png(img_path, tgt['palette'])

    if W!=tgt['W'] or H!=tgt['H']:
        sys.exit(f"Méret hiba: a kép {W}×{H}, de a portré {tgt['W']}×{tgt['H']} kell")

    # Tömörítés
    print(f"Tömörítés ({W}×{H})...")
    buf,hp_end=make_hist_buffer(rows,W,H)
    compressed=compress(buf,init_codes)
    
    # Méret-ellenőrzés: az új stream hossza dönti el, melyik útvonal kell.
    orig_stream_len = tgt['sA'] - 20  # az eredeti tömörített stream hossza
    needs_resize = len(compressed) > orig_stream_len

    if needs_resize:
        print(f"\n  Az enkódolt kép ({len(compressed)} bájt) NEM fér el a")
        print(f"  '{target_name}' slot eredeti méretében ({orig_stream_len} bájt).")
        print(f"  → TOC-frissítős mód: a blokk megnő, a fájl végén lévő index-tábla")
        print(f"    és a rá mutató globális fejléc-pointer automatikusan frissül.")
    else:
        # PADDING (2026-06-19): ha az új stream RÖVIDEBB (vagy egyenlő), kitöltjük
        # a hiányt 0x00 bájtokkal a tömörített adat VÉGÉN, hogy a blokk mérete és
        # a TOC offsetek egyáltalán ne változzanak (a legegyszerűbb, kockázatmentes eset).
        pad_len = orig_stream_len - len(compressed)
        if pad_len > 0:
            compressed = compressed + bytes(pad_len)
            print(f"  Padding: +{pad_len} bájt (a stream rövidebb volt az eredeti slotnál; "
                  f"kitöltve, hogy a blokk mérete és a TOC offsetek ne változzanak)")

    mqrc=build_mqrc(compressed,W,H,tgt['bt'],tgt['name'],hp_end)
    print(f"  Eredeti stream: {tgt['sA']-20} bájt → Új: {len(compressed)} bájt")

    # DBI módosítása: az eredeti MQRC blokk cseréje
    pp=tgt['pp']
    old_size=28+tgt['sA']  # az eredeti blokk mérete
    new_size=len(mqrc)

    if needs_resize:
        new_data = resize_patch_toc(orig_data, pp, old_size, mqrc)
        bad = verify_dbi_toc(new_data)
        # a már korábban is ismert, ettől a változástól független bt=197 anomáliát figyelmen kívül hagyjuk
        bad_new = [b for b in bad if not (b[0]=='bad_link' and b[2]['next_bt']==197)]
        if bad_new:
            print(f"  ⚠ FIGYELEM: a TOC-frissítés után {len(bad_new)} gyanús bejegyzés található "
                  f"(részletek: cmd_encode utáni verify_dbi_toc hívással ellenőrizhető).")
        else:
            print(f"  TOC-ellenőrzés: OK (minden bejegyzés konzisztens)")
    else:
        new_data=orig_data[:pp]+mqrc+orig_data[pp+old_size:]

    # Mentés
    out_path=dbi_path.replace('.DBI','_mod.DBI').replace('.dbi','_mod.dbi')
    if out_path==dbi_path: out_path=dbi_path+'.mod'
    with open(out_path,'wb') as f: f.write(new_data)
    print(f"  Mentve: {out_path}")
    print(f"  (A blokk {'+' if new_size>=old_size else ''}{new_size-old_size} bájt)")

    # Ellenőrzés: visszaolvassuk
    print("Ellenőrzés...")
    hist_v, hp_v = decompress(compressed, init_codes, hp_end)
    rows_v, _ = _rebuild_rows_v2_with_patches(hist_v, W, H, hp_v)
    ok = all(bytes(rows_v[r]) == bytes(rows[r][:W]) for r in range(H))
    print(f"  Pixel egyezés: {'100% OK ✓' if ok else 'HIBA!'}")

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv)<2 or sys.argv[1] in ('-h','--help','help'):
        print(__doc__)
        sys.exit(0)

    cmd=sys.argv[1].lower()

    if cmd=='list' and len(sys.argv)>=4:
        cmd_list(sys.argv[2], sys.argv[3])

    elif cmd=='decode' and len(sys.argv)>=5:
        cmd_decode(sys.argv[2], sys.argv[3], sys.argv[4])

    elif cmd in ('encode', 'insert') and len(sys.argv)>=5:
        # python script.py encode kep.png UNIT.DBI IMGGRAB.BIN [PREFIX+INDEX, pl. FN150]
        # ('insert' megtartva alias-ként a korábbi szkriptek/megszokás miatt)
        img_, dbi_, imggrab_ = sys.argv[2], sys.argv[3], sys.argv[4]
        prefix_, forced_idx_ = 'GP', None
        if len(sys.argv) >= 6:
            m = re.match(r'^([A-Za-z]+)(\d+)$', sys.argv[5])
            if not m:
                sys.exit(f"Hibás prefix+index formátum: '{sys.argv[5]}' (pl. helyes: FN150)")
            prefix_, forced_idx_ = m.group(1).upper(), int(m.group(2))
        cmd_insert(img_, dbi_, imggrab_, prefix_, forced_idx_)

    elif cmd=='replace' and len(sys.argv)>=6:
        # python script.py replace kep.png UNIT.DBI CÉLNÉV IMGGRAB.BIN
        # (a korábbi 'encode' viselkedés - egy MEGLÉVŐ, név szerint megadott
        # slot lecserélése, méretkorlát nélkül)
        cmd_encode(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])

    else:
        print(__doc__)
        sys.exit(1)

if __name__=='__main__':
    main()
