#!/usr/bin/env python3
"""
Aaron Owl — Roster matcher (bilingual EN / עברית)  ·  runs on the TEACHER's machine
==================================================================================
Purpose: find NON-USERS — students who SAT THE EXAM but never used the platform —
so the analysis can ask "does using Aaron Owl relate to the grade?".

The platform only knows students who generated activity (they appear, by email, in
student_features_<course>_federation.csv). Your full exam roster also contains
students with NO activity. This tool matches the roster to emails and flags who is
an app-user vs a non-user. Everything stays on your machine.

You provide two files:
  --roster    כל הנבחנים / all exam sitters.  columns: name,grade[,moed_b]
  --directory מיפוי שם→אימייל / name→email map from your LMS.  columns: name,email
              (skip this if your roster already has an `email` column)
And the package's feature file:
  --features  student_features_<course>_federation.csv   (app-users, by email)

Output: roster_matched.csv  (email, grade, moed_b, is_app_user)  → feed to
        analysis_script_v2.py --roster roster_matched.csv

Matching is ORDER-INDEPENDENT token-set matching, so "כהן דוד" == "David Cohen"-style
surname/given swaps are handled, and it works for Hebrew and English names alike.
"""
import argparse
import re
import unicodedata
import pandas as pd

# Hebrew niqqud (vowel points) + cantillation — stripped so spelling variants match
_HE_MARKS = {chr(c) for c in range(0x0591, 0x05C8)} | {chr(0x05C1), chr(0x05C2)}


def norm_tokens(s):
    """Normalize a name to an order-independent set of tokens (EN + HE safe)."""
    s = unicodedata.normalize('NFKD', str(s).strip())
    s = ''.join(ch for ch in s if ch not in _HE_MARKS)
    s = s.replace('"', '').replace("'", '').replace('״', '').replace('׳', '')
    s = s.replace('־', ' ').replace('-', ' ').lower()      # maqaf / hyphen → space
    s = re.sub(r'\s+', ' ', s)
    return frozenset(t for t in s.split() if t)


def build_index(df, name_col, email_col):
    idx = {}
    for _, r in df.iterrows():
        t = norm_tokens(r[name_col])
        if t:
            idx.setdefault(t, str(r[email_col]).strip().lower())
    return idx


def match_one(name, idx):
    """Exact token-set first; else a unique subset match sharing ≥2 tokens."""
    t = norm_tokens(name)
    if t in idx:
        return idx[t]
    cands = {e for tt, e in idx.items() if (t <= tt or tt <= t) and len(t & tt) >= 2}
    return next(iter(cands)) if len(cands) == 1 else None


def _col(df, *names):
    low = {c.strip().lower(): c for c in df.columns}
    for n in names:
        if n in low:
            return low[n]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--roster', required=True, help='all exam sitters: name,grade[,moed_b]')
    ap.add_argument('--directory', help='name→email map (name,email); omit if roster has email')
    ap.add_argument('--features', required=True, help='student_features_<course>_federation.csv')
    ap.add_argument('--out', default='roster_matched.csv')
    a = ap.parse_args()

    roster = pd.read_csv(a.roster)
    feats = pd.read_csv(a.features)
    app_emails = set(feats[_col(feats, 'email', 'student_id') or feats.columns[0]]
                     .astype(str).str.lower().str.strip())

    name_c = _col(roster, 'name', 'שם', 'student', 'full_name')
    grade_c = _col(roster, 'grade', 'final', 'final grade', 'moed_a', 'ציון', 'final_grade')
    email_c = _col(roster, 'email', 'אימייל', 'mail')
    moedb_c = _col(roster, 'moed_b', "מועד ב", 'moedb')

    # resolve an email for every roster row
    if email_c is not None:
        roster['_email'] = roster[email_c].astype(str).str.lower().str.strip()
        matched, unmatched = roster, pd.DataFrame()
    else:
        if not a.directory:
            raise SystemExit("roster has no email column → provide --directory name,email map")
        d = pd.read_csv(a.directory)
        idx = build_index(d, _col(d, 'name', 'שם', '$name') or d.columns[0],
                          _col(d, 'email', 'אימייל', '$email') or d.columns[1])
        roster['_email'] = roster[name_c].map(lambda n: match_one(n, idx))
        unmatched = roster[roster['_email'].isna()]
        matched = roster[roster['_email'].notna()].copy()

    out = pd.DataFrame({'email': matched['_email']})
    out['grade'] = pd.to_numeric(matched[grade_c], errors='coerce') if grade_c else pd.NA
    if moedb_c:
        out['moed_b'] = pd.to_numeric(matched[moedb_c], errors='coerce')
    out = out.drop_duplicates('email')
    out['is_app_user'] = out['email'].isin(app_emails)
    out.to_csv(a.out, index=False)

    n_user = int(out['is_app_user'].sum()); n_non = int((~out['is_app_user']).sum())
    print(f"roster rows={len(roster)}  matched to email={len(out)}  unmatched={len(unmatched)}")
    print(f"  app-users (in features): {n_user}")
    print(f"  NON-USERS (sat exam, no app): {n_non}")
    if len(unmatched):
        col = name_c or roster.columns[0]
        print(f"  unmatched names (fix by hand / add email): {unmatched[col].head(10).tolist()}")
    print(f"wrote {a.out}  →  next: analysis_script_v2.py --roster {a.out}")


if __name__ == '__main__':
    main()
