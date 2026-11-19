# GRG-4361u WAN Setting Tool V1.0.3 (Pilot)

## Purpose
Configure ONLY `nas0_0` to VLAN 160 / 802.1p 0 / IPoE / INTERNET / transparent bridge enabled / Fixed IP `192.168.2.121` / gateway `192.168.2.100` / mask `255.255.255.0` / **Multicast VLAN ID 160** / LAN_1 (10GE) enabled.

## Using the build
1. Upload the Clean GitHub Upload package **contents** to a separate GitHub repository.
2. GitHub Actions workflow `GRG4361 WAN Windows Build` compiles Windows EXE with Python 3.11.
3. Run Read & Compare before any write.
4. Experimental Apply & Verify requires confirmation. Use only a recovery-ready lab DUT.
5. Verify settings by reopening the actual device Web GUI after writing.

## Known limitations
- `multicast_vid` field is hidden by default in some GUI states. Submission of `160` has NOT yet been proven to persist on the device.
- Readback parser cannot verify Multicast VLAN, Static IP, bridge checkbox, or port mapping. Status remains UNKNOWN and whole-operation VERIFY_INCOMPLETE rather than PASS.
- There is no tested automatic rollback. Device-side persistence after reboot is unverified.
- No factory/production deployment until device-side verification.

## Security
Do not share live CSRF tokens or credentials. Program obtains a fresh token for each write.
