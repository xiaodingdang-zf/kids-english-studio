#!/bin/sh
# VSCO 2 Community Edition, CC0-1.0.
# Official source: https://github.com/sgossner/VSCO-2-CE
# License: https://github.com/sgossner/VSCO-2-CE/blob/master/LICENSE
set -eu
COMMIT=440300901dfe9275fd84e0b7763af1f8443ae62e
BASE="https://raw.githubusercontent.com/sgossner/VSCO-2-CE/$COMMIT"
DEST="${KES_SAMPLE_DIR:-$HOME/kes-env/samples}"
mkdir -p "$DEST"

fetch() {
  rel="$1"
  name=$(basename "$rel")
  url_rel=$(printf '%s' "$rel" | sed 's/ /%20/g')
  if [ ! -s "$DEST/$name" ]; then
    curl --fail --location --retry 2 --silent --show-error \
      "$BASE/$url_rel" -o "$DEST/$name.part"
    mv "$DEST/$name.part" "$DEST/$name"
  fi
  printf '%s\n' "$DEST/$name"
}

for name in KSHarp_E3_mf.wav KSHarp_G3_mf.wav KSHarp_F4_mf.wav KSHarp_C5_mf.wav; do
  fetch "Strings/Harp/$name"
done
for name in LLVln_Pizz_G3_f_RR1.wav LLVln_Pizz_C4_f_RR1.wav LLVln_Pizz_E4_f_RR1.wav LLVln_Pizz_A4_f_RR1.wav LLVln_Pizz_C5_f_RR1.wav; do
  fetch "Strings/Solo Violin/Pizz/$name"
done
for name in glock_medium_G4.wav glock_medium_C5.wav; do
  fetch "Percussion/Glock/$name"
done
for name in Marimba_hit_Outrigger_C4_loud_01.wav Marimba_hit_Outrigger_G4_loud_01.wav; do
  fetch "Percussion/Marimba/$name"
done
fetch "Woodwinds/Flute/expvib/LDFlute_expvib_A4_v1_1.wav"

if [ ! -s "$DEST/VSCO-2-CE-LICENSE" ]; then
  curl --fail --location --retry 2 --silent --show-error \
    "$BASE/LICENSE" -o "$DEST/VSCO-2-CE-LICENSE.part"
  mv "$DEST/VSCO-2-CE-LICENSE.part" "$DEST/VSCO-2-CE-LICENSE"
fi
