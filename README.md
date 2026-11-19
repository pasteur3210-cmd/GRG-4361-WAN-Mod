# GRG-4361u WAN Setting Tool V1.0.1 (Pilot)

## Intended nas0_0 target
VLAN 160; 802.1p display 0 (POST `vprio=1`); Channel IPoE; Bridge enabled / transparent; INTERNET service; Fixed IP 192.168.2.121; gateway 192.168.2.100; mask 255.255.255.0; DNS request off; 10GE port mapping enabled. Other WAN links must not change.

## Usage
1. Use the **Clean GitHub Upload ZIP** contents at repo root; GitHub Actions builds Windows EXE with Python 3.11.
2. Run EXE on Windows 11; enter DUT address and credentials.
3. Click **Read & Compare** first. Basic WAN fields from the existing JavaScript parser are shown as MATCH/DIFF; Static IP, Bridge checkbox and port mapping show UNKNOWN until a reliable firmware-specific readback is implemented.
4. Do not use experimental Apply in production. It sends a real HTTP POST and may disconnect/alter DUT. Requires backup, tested recovery, a disposable test DUT, and operator confirmation. A device success message cannot establish complete success; no PASS is issued for unverified settings.
5. Records are written into `records/`: cumulative Excel/CSV Master Record, execution log and JSON snapshots. Do not publish records containing equipment configuration without review.

## Limitations
The uploaded HTML contains the `ethwan` form structure, but not the router's JavaScript applyCheck() implementation or an actual successful browser POST trace. Some fields are dynamically initialized by firmware JavaScript, hence DOM markup alone cannot prove the live target. The V1.0.1 POST is a candidate only; browser-compatible serialization, `postSecurityFlag`, checkbox semantics, static IP and 10GE behavior must be validated on a recoverable test DUT. No verified rollback. No production approval.
