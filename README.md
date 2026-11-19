# GRG-4361u WAN Setting Tool V1.0.4 — Pilot

## Usage
1. Upload Clean GitHub ZIP contents to your WAN-tool repository, build via GitHub Actions.
2. Read & Compare; GUI shows overall result and MATCH/DIFF/UNKNOWN counts.
3. On recoverable TEST DUT ONLY, explicitly confirm Experimental Apply & Verify.
4. Refresh DUT Web GUI nas0_0. Inspect VLAN 160, Multicast VLAN 160, INTERNET/IPoE, Bridge, Fixed IP 192.168.2.121, Gateway 192.168.2.100, Mask 255.255.255.0, DNS, and 10GE Port Mapping.
5. Press Manual Web GUI Review, record reviewer/decision/notes. Manual review is separate from automatic result.

**Result meaning**: OK: all automatically readable fields match and no UNKNOWN; NG: a definitive mismatch or apply error; VERIFY_INCOMPLETE: at least one field could not be reliably read back. MANUAL_OK is not an automatic PASS.

## Safety
WAN writing modifies live device settings. No verified rollback. Do not deploy to production until automatic complete readback and firmware compatibility validated. Credentials and tokens must not be put into logs.

## Output
`records/WAN_Master_Record.xlsx`, `WAN_Master_Record.csv`, `before.json`, `after.json`, `read_comparison.json`, `after_comparison.json`, `manual_reviews.jsonl`, `execution.log`.
